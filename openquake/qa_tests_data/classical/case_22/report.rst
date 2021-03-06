Classical PSHA using Alaska 2007 active shallow crust grid model
================================================================

============== ===================
checksum32     3,294,662,884      
date           2018-10-05T03:05:03
engine_version 3.3.0-git48e9a474fd
============== ===================

num_sites = 21, num_levels = 114

Parameters
----------
=============================== ==================
calculation_mode                'classical'       
number_of_logic_tree_samples    0                 
maximum_distance                {'default': 200.0}
investigation_time              50.0              
ses_per_logic_tree_path         1                 
truncation_level                3.0               
rupture_mesh_spacing            4.0               
complex_fault_mesh_spacing      4.0               
width_of_mfd_bin                0.1               
area_source_discretization      10.0              
ground_motion_correlation_model None              
minimum_intensity               {}                
random_seed                     23                
master_seed                     0                 
ses_seed                        42                
=============================== ==================

Input files
-----------
======================= ================================================================
Name                    File                                                            
======================= ================================================================
gsim_logic_tree         `gmpe_logic_tree.xml <gmpe_logic_tree.xml>`_                    
job_ini                 `job.ini <job.ini>`_                                            
sites                   `sites.csv <sites.csv>`_                                        
source                  `Alaska_asc_grid_NSHMP2007.xml <Alaska_asc_grid_NSHMP2007.xml>`_
source                  `extra_source_model.xml <extra_source_model.xml>`_              
source_model_logic_tree `source_model_logic_tree.xml <source_model_logic_tree.xml>`_    
======================= ================================================================

Composite source model
----------------------
========================= ======= =============== ================
smlt_path                 weight  gsim_logic_tree num_realizations
========================= ======= =============== ================
Alaska_asc_grid_NSHMP2007 1.00000 simple(4)       4/4             
========================= ======= =============== ================

Required parameters per tectonic region type
--------------------------------------------
====== ======================================================================================================= ========= ========== =======================
grp_id gsims                                                                                                   distances siteparams ruptparams             
====== ======================================================================================================= ========= ========== =======================
0      AbrahamsonSilva1997() CampbellBozorgnia2003NSHMP2007() SadighEtAl1997() YoungsEtAl1997SInterNSHMP2008() rjb rrup  vs30       dip hypo_depth mag rake
1      AbrahamsonSilva1997() CampbellBozorgnia2003NSHMP2007() SadighEtAl1997() YoungsEtAl1997SInterNSHMP2008() rjb rrup  vs30       dip hypo_depth mag rake
====== ======================================================================================================= ========= ========== =======================

Realizations per (TRT, GSIM)
----------------------------

::

  <RlzsAssoc(size=4, rlzs=4)
  1,AbrahamsonSilva1997(): [0]
  1,CampbellBozorgnia2003NSHMP2007(): [1]
  1,SadighEtAl1997(): [2]
  1,YoungsEtAl1997SInterNSHMP2008(): [3]>

Number of ruptures per tectonic region type
-------------------------------------------
==================================================== ====== ==================== ============ ============
source_model                                         grp_id trt                  eff_ruptures tot_ruptures
==================================================== ====== ==================== ============ ============
Alaska_asc_grid_NSHMP2007.xml extra_source_model.xml 1      Active Shallow Crust 368          1,104       
==================================================== ====== ==================== ============ ============

Slowest sources
---------------
====== ========= ==== ===== ===== ============ ========= ========== ========= ========= ======
grp_id source_id code gidx1 gidx2 num_ruptures calc_time split_time num_sites num_split weight
====== ========= ==== ===== ===== ============ ========= ========== ========= ========= ======
0      1         M    0     2     160          0.0       0.0        0.0       0         0.0   
1      2         M    0     12    1,104        0.0       0.00396    0.0       4         0.0   
====== ========= ==== ===== ===== ============ ========= ========== ========= ========= ======

Computation times by source typology
------------------------------------
==== ========= ======
code calc_time counts
==== ========= ======
M    0.0       2     
==== ========= ======

Duplicated sources
------------------
There are no duplicated sources

Information about the tasks
---------------------------
================== ======= ========= ======= ======= =======
operation-duration mean    stddev    min     max     outputs
read_source_models 0.00242 8.787E-04 0.00180 0.00304 2      
split_filter       0.00549 NaN       0.00549 0.00549 1      
================== ======= ========= ======= ======= =======

Data transfer
-------------
================== ======================================================================= ========
task               sent                                                                    received
read_source_models monitor=662 B converter=638 B fnames=383 B                              6.78 KB 
split_filter       srcs=5.01 KB monitor=343 B srcfilter=253 B sample_factor=21 B seed=14 B 3.01 KB 
================== ======================================================================= ========

Slowest operations
------------------
======================== ======== ========= ======
operation                time_sec memory_mb counts
======================== ======== ========= ======
updating source_info     0.01131  0.0       1     
total split_filter       0.00549  0.0       1     
total read_source_models 0.00484  0.0       2     
======================== ======== ========= ======