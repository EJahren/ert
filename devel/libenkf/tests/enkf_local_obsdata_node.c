/*
   Copyright (C) 2013  Statoil ASA, Norway. 
    
   The file 'enkf_local_obsdata_node.c' is part of ERT - Ensemble based Reservoir Tool. 
    
   ERT is free software: you can redistribute it and/or modify 
   it under the terms of the GNU General Public License as published by 
   the Free Software Foundation, either version 3 of the License, or 
   (at your option) any later version. 
    
   ERT is distributed in the hope that it will be useful, but WITHOUT ANY 
   WARRANTY; without even the implied warranty of MERCHANTABILITY or 
   FITNESS FOR A PARTICULAR PURPOSE.   
    
   See the GNU General Public License at <http://www.gnu.org/licenses/gpl.html> 
   for more details. 
*/
#include <stdlib.h>
#include <stdbool.h>
#include <stdio.h>
#include <unistd.h>

#include <ert/util/test_util.h>
#include <ert/util/int_vector.h>

#include <ert/enkf/local_obsdata_node.h>
#include <ert/enkf/active_list.h>


void test_content( local_obsdata_node_type * node ) {
  active_list_type * active_list = local_obsdata_node_get_active_list( node );
  test_assert_not_NULL( active_list );
  test_assert_true( active_list_is_instance( active_list ));
  
  test_assert_true( int_vector_is_instance( local_obsdata_node_get_tstep_list( node )));
}


int main(int argc , char ** argv) {
  const char * obs_key = "1234";

  {
    local_obsdata_node_type * node = local_obsdata_node_alloc( obs_key );
    
    test_assert_true( local_obsdata_node_is_instance( node ));
    test_assert_string_equal( obs_key , local_obsdata_node_get_key( node ));
    test_content( node );
    local_obsdata_node_free( node );
  }

  {
    void * node = local_obsdata_node_alloc( obs_key );
    local_obsdata_node_free__( node );
  }
  
  exit(0);
}

