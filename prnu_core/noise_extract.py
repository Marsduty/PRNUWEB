import numpy as np
import pywt
from .prnu_utils import get_daubechies_8_wavelet, wiener_noise_extract

def extract_noise(image, sigma=3.0, level=4):
    """
    对应 MATLAB 的 NoiseExtract.m
    提取局部高斯噪声残差 N(0, sigma^2)
    """
    image = image.astype(np.float64)
    M, N = image.shape
    m = 2 ** level
    
    # 1. 严格复现 MATLAB 的镜像 Padding 逻辑
    minpad = 2
    nr = int(np.ceil((M + minpad) / m) * m)
    nc = int(np.ceil((N + minpad) / m) * m)
    pr = int(np.ceil((nr - M) / 2))
    prd = int(np.floor((nr - M) / 2))
    pc = int(np.ceil((nc - N) / 2))
    pcr = int(np.floor((nc - N) / 2))
    
    # numpy.pad(mode='symmetric') 与 MATLAB 的镜像机制等效
    padded_img = np.pad(image, ((pr, prd), (pc, pcr)), mode='symmetric')
    
    # 2. 小波分解
    wavelet = get_daubechies_8_wavelet()
    noise_var = sigma ** 2
    
    # wavedec2 返回格式：[cA_n, (cH_n, cV_n, cD_n), ..., (cH_1, cV_1, cD_1)]
    coeffs = pywt.wavedec2(padded_img, wavelet, mode='periodization', level=level)
    
    # 3. 对每一层的细节系数（cH, cV, cD）提取噪声
    new_coeffs = [coeffs[0] * 0] # 最低频(LL)分量置0
    
    for idx in range(1, level + 1):
        cH, cV, cD = coeffs[idx]
        
        # 应用维纳 MAP 去噪估计残差
        cH_noise = wiener_noise_extract(cH, noise_var)
        cV_noise = wiener_noise_extract(cV, noise_var)
        cD_noise = wiener_noise_extract(cD, noise_var)
        
        new_coeffs.append((cH_noise, cV_noise, cD_noise))
    
    # 4. 小波逆变换重构残差图像
    noise_spatial = pywt.waverec2(new_coeffs, wavelet, mode='periodization')
    
    # 5. 裁剪回原始尺寸
    extracted_noise = noise_spatial[pr:pr+M, pc:pc+N]
    
    return extracted_noise
