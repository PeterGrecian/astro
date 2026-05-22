#!/usr/bin/env python3
import numpy as np
from astropy.io import fits

# 1. Load the raw numpy array
# The OV5647 sensor outputs a 2592 x 1944 image array
bayer_data = np.load("pi_v1_image.npy")

# Ensure the data type is correct for 10-bit integer storage
# Raspberry Pi raw data usually gets unpacked into uint16 arrays
if bayer_data.dtype != np.uint16:
    bayer_data = bayer_data.astype(np.uint16)

# 2. Create the primary empty HDU 
primary_hdu = fits.PrimaryHDU()

# 3. Create the Rice-compressed HDU for the raw science data
# Rice handles the 10-bit integer depth with 100% mathematical losslessness
sci_hdu = fits.CompImageHDU(data=bayer_data, compression_type='RICE_1', name="SCI")

# 4. Inject strict hardware metadata into the FITS header
# This tells any software (PixInsight, Siril, AstroImageJ) how to read the file
sci_hdu.header['TELESCOP'] = 'Raspberry Pi Camera V1'
sci_hdu.header['INSTRUME'] = 'OmniVision OV5647'
sci_hdu.header['BAYERPAT'] = 'BGGR'         # The exact Bayer layout of the Pi V1 sensor
sci_hdu.header['BITDEPTH'] = 10             # Hardware bit depth
sci_hdu.header['ROWORDER'] = 'TOP-DOWN'     # Prevents the image from loading upside down

# 5. Combine and save
hdu_list = fits.HDUList([primary_hdu, sci_hdu])
hdu_list.writeto("pi_v1_compressed.fits", overwrite=True)

print("Pi V1 FITS conversion complete!")

