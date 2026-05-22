#!/usr/bin/env python3

import glob, os, time
import numpy as np
import sys

for f in glob.glob("*"): 
    print( f, np.load(glob.glob(f+"/*")[0]).mean(), np.load(glob.glob(f+"/*")[-1]).mean())

