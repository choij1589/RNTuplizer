# source me: CMSSW_15_0_22 (PyROOT) for local and condor use
export SCRAM_ARCH=el9_amd64_gcc12
source /cvmfs/cms.cern.ch/cmsset_default.sh
QC_ROOT=${QC_ROOT:-/d0/scratch/choij/SampleFactoryQC}
if [ ! -d $QC_ROOT/cmssw/CMSSW_15_0_22 ]; then (cd $QC_ROOT/cmssw && scramv1 project CMSSW CMSSW_15_0_22); fi
cd $QC_ROOT/cmssw/CMSSW_15_0_22/src && eval $(scramv1 runtime -sh)
cd - >/dev/null
