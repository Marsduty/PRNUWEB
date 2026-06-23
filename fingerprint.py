import numpy as np
from noise_extract import extract_noise
from prnu_utils import inten_scale, saturation, rgb2gray1
from enhancers import rsc, sea, dc, hf, gf

def _validate_ready_images(ready_images):
    images = list(ready_images)
    if not images:
        raise ValueError("传入的图像列表为空！")

    first_shape = None
    for index, image in enumerate(images):
        if not isinstance(image, np.ndarray):
            raise TypeError(f"Image {index} must be a numpy.ndarray")
        if image.ndim != 3 or image.shape[2] != 3:
            raise ValueError(f"Image {index} must be an RGB array with shape (height, width, 3)")
        if first_shape is None:
            first_shape = image.shape
        elif image.shape != first_shape:
            raise ValueError(f"All images must have the same shape; image 0 is {first_shape}, image {index} is {image.shape}")
    return images


def get_fingerprint(ready_images, enh_list=(1, 0, 0, 0, 0)):
    """
    提取并融合设备的参考 PRNU 指纹。
    
    参数:
    ready_images: 包含 RGB 图像(已裁剪为统一尺寸)的 numpy 数组列表
    enh_list: 增强算法开关列表 [RSC, SEA, DC, HF, GF]
    
    返回:
    result: 提取并增强后的 2D 单通道 PRNU 指纹 numpy 数组
    """
    ready_images = _validate_ready_images(ready_images)
    if len(enh_list) != 5:
        raise ValueError("enh_list must contain 5 switches: [RSC, SEA, DC, HF, GF]")
    
    RPsum = None
    NN = None
    
    # 1. 遍历内存中的所有图像矩阵进行残差提取与加权
    for img in ready_images:
        # 强制转换为双精度浮点数，防止极微弱的 PRNU 高频信号在计算中发生精度截断
        img = img.astype(np.float64)
        M, N, C = img.shape
        
        # 初始化累加器
        if RPsum is None:
            RPsum = np.zeros((M, N, C), dtype=np.float64)
            NN = np.zeros((M, N, C), dtype=np.float64)
            
        # 2. 对每个颜色通道单独提取残差并计算权重
        for cc in range(3):
            img_channel = img[:, :, cc]
            
            # 实时提取高频噪声残差 (对应 MATLAB 中的 NoiseExtract)
            noise_channel = extract_noise(img_channel, sigma=3.0, level=4)
            
            # 调整噪声极性，强化指纹特征 (等效于 MATLAB: (abs(Noise).^0.5) .* sign(Noise))
            noise_channel = (np.abs(noise_channel) ** 0.5) * np.sign(noise_channel)
            
            # 计算光强权重和非饱和区域掩码
            inten = inten_scale(img_channel) * saturation(img_channel)
            
            # 按照图像内容的光强置信度进行加权累加
            RPsum[:, :, cc] += noise_channel * inten
            NN[:, :, cc] += inten ** 2

    # 3. 归一化生成初始的 3D PRNU (除以加权平方和)
    RP = np.zeros_like(RPsum)
    for cc in range(3):
        RP[:, :, cc] = RPsum[:, :, cc] / (NN[:, :, cc] + 1.0)
        
    # 4. 灰度化合并三通道 (等效于 MATLAB: rgb2gray1)
    result = rgb2gray1(RP)
    
    # 5. 后处理：显式解耦与 NUA 压制
    # 按照 [RSC, SEA, DC, HF, GF] 的顺序应用算法
    if enh_list[0] == 1:
        result = rsc(result)
    if enh_list[1] == 1:
        result = sea(result)
    if enh_list[2] == 1:
        result = dc(result)
    if enh_list[3] == 1:
        result = hf(result)
    if enh_list[4] == 1:
        result = gf(result)
    
    return result
