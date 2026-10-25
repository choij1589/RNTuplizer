#!/bin/bash
# rnt_build.sh: build bin/rnt_convert and bin/rnt_inventory with the pinned LCG view (config/rntuple_env.conf).
set -e
R=$(cd "$(dirname "$0")/.." && pwd)
source $R/scripts/env.sh
cmake -S $R -B $R/build -DRNT_PINNED_ROOT=$ROOT_VERSION -DCMAKE_BUILD_TYPE=Release >/dev/null
cmake --build $R/build -j 8 2>&1 | tail -3
cmake --install $R/build --prefix $R >/dev/null
{
  echo "built: $(date '+%F %T')"
  echo "lcg_view: $LCG_VIEW/$LCG_PLATFORM"
  echo "root: $(root-config --version)"
  echo "compiler: $(g++ --version | head -1)"
  echo "repo_commit: $(git -C $R rev-parse --short HEAD 2>/dev/null)$(git -C $R diff --quiet -- src CMakeLists.txt 2>/dev/null || echo '+dirty')"
  sha256sum $R/bin/rnt_convert $R/bin/rnt_inventory $R/bin/rnt_validate $R/bin/rnt_readbench | sed "s#$R/##"
} > $R/bin/BUILD_INFO
cat $R/bin/BUILD_INFO
