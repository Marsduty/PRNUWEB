import numpy as np
import pywt
from scipy.ndimage import uniform_filter

def get_daubechies_8_wavelet():
    """对应 MATLAB MakeONFilter('Daubechies', 8) 的自定义小波"""
    # MATLAB 中的 Par=8 对应 8 个系数 (相当于 PyWavelets 中的 db4)
    # 为了保证计算与 MATLAB 绝对一致，我们直接使用你的系数值构建自定义 Wavelet
    f = np.array([0.230377813309, 0.714846570553, 0.630880767930, -0.027983769417,
                  -0.187034811719, 0.030841381836, 0.032883011667, -0.010597401785])
    f = f / np.linalg.norm(f)
    # 在 PyWavelets 中，需要提供分解和重构的高通/低通滤波器
    # 对于正交小波，可以通过缩放函数 f 生成
    dec_lo = f
    dec_hi = dec_lo[::-1] * ((-1) ** np.arange(len(dec_lo)))
    rec_lo = dec_lo[::-1]
    rec_hi = dec_hi[::-1]
    return pywt.Wavelet('custom_db8', [dec_lo, dec_hi, rec_lo, rec_hi])

def wiener_noise_extract(coef, noise_var):
    """对应 MATLAB 中的 WaveNoise 函数：局部方差 MAP 估计去噪"""
    tc = coef ** 2
    # 3x3 窗口
    coef_var = np.maximum(0, uniform_filter(tc, size=3) - noise_var)
    # 5x5 到 9x9 窗口寻找最小方差估计
    for w in [5, 7, 9]:
        est_var = np.maximum(0, uniform_filter(tc, size=w) - noise_var)
        coef_var = np.minimum(coef_var, est_var)
    
    # 维纳滤波衰减
    return coef * noise_var / (coef_var + noise_var)

def inten_scale(image):
    """光强加权函数 (等效于 IntenScale)"""
    # 抑制极暗区域的噪声
    return np.exp(-0.5 * ((image - 128) / 64) ** 2)

def saturation(image):
    """饱和像素掩码 (等效于 Saturation)"""
    # 剔除完全过曝(255)和死黑(0)的像素，这些区域PRNU往往被截断
    return (image > 0) & (image < 255)

def rgb2gray1(rp):
    """将三通道的 PRNU 指纹合并为单通道 (等效于 rgb2gray1)"""
    # 使用标准亮度公式，防止精度丢失
    return 0.299 * rp[:,:,0] + 0.587 * rp[:,:,1] + 0.114 * rp[:,:,2]