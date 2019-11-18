import pandas as pd

from res.enkf.export import (
    GenDataCollector,
    SummaryCollector,
    SummaryObservationCollector,
)
from res.enkf.plot_data import PlotBlockDataLoader


class MeasuredData(object):
    def __init__(self, ert, keys, index_lists=None):
        if index_lists is None:
            index_lists = [None] * len(keys)
        self.data = self._get_data(ert, keys, index_lists)

    def remove_nan_and_filter(self, keys, std_cutoff, alpha):
        self.remove_nan()
        self.filter_out_outliers(keys, std_cutoff, alpha)

    def remove_nan(self):
        """
        Removes NaN values from the case, first on a row basis to remove failed realizations,
        then on a column basis.
        """
        self.data[~self.data.index.isin(["OBS", "STD"])] = self.data[
            ~self.data.index.isin(["OBS", "STD"])
        ].dropna(axis=0, how="all")
        self.data = self.data.dropna(axis=1)
        if self.data.shape[1] == 0:
            raise ValueError("Empty dataset, all data has been filtered out")

    @staticmethod
    def filter_on_column_index(dataframe, index_list):
        return MeasuredData._filter_on_column_index(dataframe, index_list)

    def filter_out_outliers(self, keys, std_cutoff, alpha):
        self.data = self._filter_out_outliers(keys, std_cutoff, alpha)

    def _get_data(self, ert, observation_keys, index_lists):
        """
        Adds simulated and observed data and returns a dataframe where ensamble members will
        have a data key, observed data will be named OBS and observated standard
        deviation will be named STD.
        """
        measured_data = pd.DataFrame()
        case_name = ert.getEnkfFsManager().getCurrentFileSystem().getCaseName()
        for key, index_list in zip(observation_keys, index_lists):
            observation_type = ert.getObservations()[key].getImplementationType().name
            if observation_type == "GEN_OBS":
                measured_data = pd.concat(
                    [
                        measured_data,
                        self._get_general_data(ert, key, index_list, case_name),
                    ],
                    axis=1,
                )
            elif observation_type == "SUMMARY_OBS":
                measured_data = pd.concat(
                    [
                        measured_data,
                        self._get_summary_data(ert, key, index_list, case_name),
                    ],
                    axis=1,
                )
            elif observation_type == "BLOCK_OBS":
                measured_data = pd.concat(
                    [
                        measured_data,
                        self._get_block_data(
                            ert.getObservations(),
                            key,
                            index_list,
                            ert.getEnsembleSize(),
                            ert.getEnkfFsManager().getCurrentFileSystem(),
                        ),
                    ],
                    axis=1,
                )
            else:
                raise TypeError("Unknown observation type: {}".format(observation_type))
        return measured_data

    def _get_block_data(self, observations, key, index_list, ensamble_size, storage):
        obs_vector = observations[key]
        loader = PlotBlockDataLoader(obs_vector)

        data = pd.DataFrame()
        for report_step in obs_vector.getStepList().asList():

            block_data = loader.load(storage, report_step)
            obs_block = loader.getBlockObservation(report_step)

            data = (
                data.append(
                    pd.DataFrame(
                        [self._get_block_observations(obs_block.getValue, obs_block)],
                        index=["OBS"],
                    )
                )
                .append(
                    pd.DataFrame(
                        [self._get_block_observations(obs_block.getStd, obs_block)],
                        index=["STD"],
                    )
                )
                .append(self._get_block_measured(ensamble_size, block_data))
            )
        data = MeasuredData.filter_on_column_index(data, index_list)
        data = pd.concat({key: data}, axis=1)
        return data

    def _get_general_data(self, ert, observation_key, index_list, case_name):
        ert_obs = ert.getObservations()
        data_key = ert_obs[observation_key].getDataKey()

        general_data = pd.DataFrame()

        for time_step in ert_obs[observation_key].getStepList().asList():
            data = GenDataCollector.loadGenData(ert, case_name, data_key, time_step)

            general_data = (
                general_data.append(
                    pd.DataFrame(
                        self._get_observations(ert_obs, observation_key), index=["OBS"]
                    )
                )
                .append(
                    pd.DataFrame(self._get_std(ert_obs, observation_key), index=["STD"])
                )
                .append(
                    pd.concat(
                        [
                            pd.DataFrame([data[key]], index=[observation_key])
                            for key in data.keys()
                        ]
                    )
                )
            )
        general_data = MeasuredData.filter_on_column_index(general_data, index_list)
        general_data = pd.concat({observation_key: general_data}, axis=1)
        return general_data

    @staticmethod
    def _filter_on_column_index(dataframe, index_list):
        """
        Retuns a subset where the columns in index_list are filtered out
        """
        if isinstance(index_list, (list, tuple)):
            if max(index_list) > dataframe.shape[1]:
                msg = (
                    "Index list is larger than observation data, please check input, max index list:"
                    "{} number of data points: {}".format(
                        max(index_list), dataframe.shape[1]
                    )
                )
                raise IndexError(msg)
            return dataframe.iloc[:, list(index_list)]
        else:
            return dataframe

    def _filter_out_outliers(self, keys, std_cutoff, alpha):
        """
        Goes through the observation keys and filters out outliers. It first extracts
        key data such as ensamble mean and std, and observation values and std. It creates
        a filtered index which is a pandas series of indexes where the data will be removed.
        This can have duplicates of indicies.
        """
        filters = []

        for key in keys:
            ens_data = self.data[key][~self.data[key].index.isin(["OBS", "STD"])]

            ens_mean = ens_data.mean(axis=0)
            ens_std = ens_data.std(axis=0)
            obs_values = self.data[key].loc["OBS"]
            obs_std = self.data[key].loc["STD"]

            filters.append(self._filter_ensamble_std(ens_std, std_cutoff))
            filters.append(
                self._filter_ens_mean_obs(ens_mean, ens_std, obs_values, obs_std, alpha)
            )

        combined_filter = self._combine_filters(filters)
        return self.data.drop(columns=combined_filter[combined_filter].index)

    def _get_summary_data(self, ert, observation_key, index_list, case_name):
        data_key = ert.getObservations()[observation_key].getDataKey()
        data = pd.concat(
            [
                self._add_summary_observations(ert, data_key, case_name),
                self._add_summary_data(ert, data_key, case_name),
            ]
        )
        data = MeasuredData.filter_on_column_index(data, index_list)
        return pd.concat({observation_key: data}, axis=1)

    @staticmethod
    def _filter_ensamble_std(ensamble_std, std_cutoff):
        """
        Filters on ensamble variation versus a user defined standard
        deviation cutoff.
        """
        return ensamble_std < std_cutoff

    @staticmethod
    def _filter_ens_mean_obs(
        ensamble_mean, ensamble_std, observation_values, observation_std, alpha
    ):
        """
        Filters on distance between the observed data and the ensamble mean based on variation and
        a user defined alpha.
        """
        return abs(observation_values - ensamble_mean) > alpha * (
            ensamble_std + observation_std
        )

    @staticmethod
    def _combine_filters(filters):
        combined_filter = pd.Series()
        for filter in filters:
            combined_filter = filter | combined_filter
        return combined_filter

    @staticmethod
    def _add_summary_data(ert, data_key, case_name):
        data = SummaryCollector.loadAllSummaryData(ert, case_name, [data_key])
        data = data[data_key].unstack(level=-1)
        return data.set_index(data.index.values)

    @staticmethod
    def _add_summary_observations(ert, data_key, case_name):
        data = SummaryObservationCollector.loadObservationData(
            ert, case_name, [data_key]
        ).transpose()
        data = data.set_index(
            data.index.str.replace(r"\b" + data_key, "OBS", regex=True)
        )
        return data.set_index(data.index.str.replace("_" + data_key, ""))

    @staticmethod
    def _get_block_observations(func, observation_block):
        return [func(nr) for nr in observation_block]

    @staticmethod
    def _get_block_measured(ensamble_size, block_data):
        data = pd.DataFrame()
        for ensamble_nr in range(ensamble_size):
            data = data.append(
                pd.DataFrame([block_data[ensamble_nr]], index=[ensamble_nr])
            )
        return data

    @staticmethod
    def _get_observations(all_obs, obs_key):
        return [obs_node.get_data_points() for obs_node in all_obs[obs_key]]

    @staticmethod
    def _get_std(all_obs, obs_key):
        return [obs_node.get_std() for obs_node in all_obs[obs_key]]
