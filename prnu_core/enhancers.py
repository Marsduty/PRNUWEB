import numpy as np
from scipy.fft import fft2, ifft2, fftshift, ifftshift, dctn, idctn
from scipy.ndimage import uniform_filter, correlate

# =====================================================================
# 1. DC (Decorrelation) - 压制非唯一伪影
# =====================================================================
def dc(reference, patch_size=8, fp_var=9):
    """等效于 dc.m"""
    if reference.ndim != 2:
        raise ValueError(f"DC expects a 2D reference, got shape={reference.shape}")

    result = np.zeros_like(reference)
    rows, cols = reference.shape
    
    if rows % patch_size != 0 or cols % patch_size != 0:
        raise ValueError(f"Size {reference.shape} cannot be divided by {patch_size}!")
        
    row_patch_num = rows // patch_size
    col_patch_num = cols // patch_size
    for i in range(row_patch_num):
        for j in range(col_patch_num):
            r_sta, r_end = i * patch_size, (i + 1) * patch_size
            c_sta, c_end = j * patch_size, (j + 1) * patch_size
            
            fp_temp = reference[r_sta:r_end, c_sta:c_end]
            result[r_sta:r_end, c_sta:c_end] = _dc_preprocessing(fp_temp, fp_var)
    return result

def _dc_preprocessing(spn_patches, reference_variance):
    mean_vector = np.mean(spn_patches, axis=0)
    centered_data = spn_patches - mean_vector
    
    # 使用 SVD 等效替换 MATLAB 的 pca()
    U, S, Vt = np.linalg.svd(centered_data, full_matrices=False)
    latent = (S ** 2) / (spn_patches.shape[0] - 1)
    coeff = Vt.T
    score = U * S
    
    attenuated_data = np.copy(score)
    for i, eigenvalue in enumerate(latent):
        if eigenvalue > reference_variance:
            attenuation_factor = reference_variance * (
                1 + (eigenvalue - reference_variance) * np.exp(reference_variance - eigenvalue)
            ) / eigenvalue
            attenuated_data[:, i] = score[:, i] * attenuation_factor
            
    processed_data = attenuated_data @ coeff.T + mean_vector
    return processed_data


# =====================================================================
# 2. GF (Guided filtering) - 导向滤波分离高低频分量
# =====================================================================
def gf(reference, r=5, eps=0.01, lambda_=5):
    """等效于 gf.m"""
    fp_low_20 = _mybandpass(reference, 20, 100, 'lowpass')
    fp_low = _guidedfilter(fp_low_20, reference, r, eps)
    return (reference - fp_low) * lambda_ + fp_low

def _boxfilter(imSrc, r):
    """O(1) 盒式滤波，严格对齐 MATLAB cumsum 的边界逻辑"""
    hei, wid = imSrc.shape
    imDst = np.zeros_like(imSrc)
    
    imCum = np.cumsum(imSrc, axis=0)
    imDst[0:r+1, :] = imCum[r:2*r+1, :]
    imDst[r+1:hei-r, :] = imCum[2*r+1:hei, :] - imCum[0:hei-2*r-1, :]
    imDst[hei-r:hei, :] = np.tile(imCum[hei-1, :], (r, 1)) - imCum[hei-2*r-1:hei-r-1, :]
    
    imCum = np.cumsum(imDst, axis=1)
    imDst[:, 0:r+1] = imCum[:, r:2*r+1]
    imDst[:, r+1:wid-r] = imCum[:, 2*r+1:wid] - imCum[:, 0:wid-2*r-1]
    imDst[:, wid-r:wid] = np.tile(imCum[:, wid-1:wid], (1, r)) - imCum[:, wid-2*r-1:wid-r-1]
    return imDst

def _guidedfilter(G, I, r, eps):
    hei, wid = G.shape
    N = _boxfilter(np.ones((hei, wid)), r)
    
    mean_G = _boxfilter(G, r) / N
    mean_I = _boxfilter(I, r) / N
    mean_GI = _boxfilter(G * I, r) / N
    
    cov_GI = mean_GI - mean_G * mean_I
    var_G = _boxfilter(G * G, r) / N - mean_G * mean_G
    
    a = cov_GI / (var_G + eps)
    b = mean_I - a * mean_G
    
    return (_boxfilter(a, r) / N) * G + (_boxfilter(b, r) / N)

def _mybandpass(image, D_low, D_high, mode):
    M, N = image.shape
    u = np.arange(-M/2, M/2)
    v = np.arange(-N/2, N/2)
    U, V = np.meshgrid(v, u) # Python 的 meshgrid(x, y) 等效于 MATLAB 的 meshgrid
    D = np.sqrt(U**2 + V**2)
    
    if mode == 'highpass':
        H = (D > D_high).astype(np.float64)
    elif mode == 'lowpass':
        H = (D < D_low).astype(np.float64)
    elif mode == 'bandpass':
        H = ((D > D_low) & (D < D_high)).astype(np.float64)
        
    J = fftshift(fft2(image))
    K = J * H
    return np.real(ifft2(ifftshift(K)))


# =====================================================================
# 3. HF (High frequency) - DCT频域高通滤波
# =====================================================================
def hf(reference, alpha=0.45):
    """等效于 hf.m"""
    l = reference.shape[0]
    l_cut = int(np.round(l * alpha))
    
    # norm='ortho' 等效于 MATLAB dct2 的正交归一化
    fp_dct = dctn(reference, norm='ortho')
    
    i_idx, j_idx = np.indices(reference.shape)
    mask = (i_idx + j_idx < l_cut) & (i_idx < l_cut) & (j_idx < l_cut)
    fp_dct[mask] = 0.0
    
    return idctn(fp_dct, norm='ortho')


# =====================================================================
# 4. RSC (Removing the Sharing Components) - 剔除CFA与共享伪影
# =====================================================================
def rsc(reference):
    """等效于 rsc.m"""
    ref_zm = _zero_mean_total(reference)
    sigmaRP = np.std(ref_zm, ddof=1) # 匹配 MATLAB std2 的 N-1 自由度
    return _wiener_in_dft(ref_zm, sigmaRP)

def _zero_mean(X, type_='CFA'):
    M, N = X.shape
    X_3d = X[:, :, np.newaxis]
    K = 1
    Y = np.zeros_like(X_3d)
    
    for j in range(K):
        mu = np.mean(X_3d[:, :, j])
        X_3d[:, :, j] -= mu
        
    col = np.mean(X_3d, axis=0) # [N, K]
    row = np.mean(X_3d, axis=1) # [M, K]
    
    if type_ in ['both', 'CFA']:
        for j in range(K):
            Y[:, :, j] = X_3d[:, :, j] - np.tile(col[:, j], (M, 1))
            Y[:, :, j] -= np.tile(row[:, j][:, np.newaxis], (1, N))
            
    if type_ == 'CFA':
        for j in range(K):
            cm = np.mean(Y[0::2, 0::2, j])
            Y[0::2, 0::2, j] -= cm
            Y[1::2, 1::2, j] -= cm
            Y[0::2, 1::2, j] += cm
            Y[1::2, 0::2, j] += cm
            
    return Y[:, :, 0]

def _zero_mean_total(X):
    Y = np.zeros_like(X)
    Y[0::2, 0::2] = _zero_mean(X[0::2, 0::2], 'both')
    Y[0::2, 1::2] = _zero_mean(X[0::2, 1::2], 'both')
    Y[1::2, 0::2] = _zero_mean(X[1::2, 0::2], 'both')
    Y[1::2, 1::2] = _zero_mean(X[1::2, 1::2], 'both')
    return Y

def _wiener_in_dft(im_noise, sigma):
    M, N = im_noise.shape
    F = fft2(im_noise)
    Fmag = np.abs(F / np.sqrt(M * N))
    
    noise_var = sigma ** 2
    tc = Fmag ** 2
    
    coef_var = np.maximum(0, uniform_filter(tc, size=3) - noise_var)
    for w in [5, 7, 9]:
        est_var = np.maximum(0, uniform_filter(tc, size=w) - noise_var)
        coef_var = np.minimum(coef_var, est_var)
        
    Fmag1 = Fmag * noise_var / (coef_var + noise_var)
    
    fzero = (Fmag == 0)
    Fmag[fzero] = 1.0
    Fmag1[fzero] = 0.0
    
    F = F * Fmag1 / Fmag
    return np.real(ifft2(F))


# =====================================================================
# 5. SEA (Spectrum Equalization Algorithm) - 频域均衡剔除峰值
# =====================================================================
def sea(reference, th=2.0):
    """等效于 sea.m"""
    rows, cols = reference.shape
    F = fftshift(fft2(reference))
    abs_F = np.abs(F)
    
    _, peaks_small, peaks_large = _spectrum_equalizer(abs_F, (17, 17), th, th + 0.3)
    
    peaks = np.zeros((rows, cols), dtype=bool)
    peaks[0::16, 0::16] = True
    peaks = (peaks & peaks_small) | peaks_large
    
    neighbour = (15, 15)
    kernel = np.ones(neighbour)
    
    # mode='wrap' 等效于 MATLAB imfilter 的 'circular'
    sum_mark = correlate((~peaks).astype(np.float64), kernel, mode='wrap')
    tmp_image = correlate(abs_F * (~peaks).astype(np.float64), kernel, mode='wrap') / (sum_mark + 1e-12)
    
    result_image = np.copy(abs_F)
    result_image[peaks] = tmp_image[peaks]
    
    new_F = ifftshift(F * (result_image / (abs_F + 1e-12)))
    return np.real(ifft2(new_F))

def _spectrum_equalizer(image, neighbour, th1, th2):
    m, n = image.shape
    mark = np.ones((m, n), dtype=bool)
    
    peaks = np.zeros((m, n, 3), dtype=bool)
    peaks[:, :, 0] = _detect_peaks(image, neighbour, mark, th1)
    for i in range(1, 3):
        peaks[:, :, i] = _detect_peaks(image, neighbour, ~peaks[:, :, i-1], th1)
        
    peaks2 = peaks[:, :, 2]
    
    peaks[:, :, 0] = _detect_peaks(image, neighbour, mark, th2)
    for i in range(1, 3):
        peaks[:, :, i] = _detect_peaks(image, neighbour, ~peaks[:, :, i-1], th2)
        
    peaks3 = peaks[:, :, 2]
    
    kernel = np.ones(neighbour)
    sum_mark = correlate((~peaks2).astype(np.float64), kernel, mode='wrap')
    tmp_image = correlate(image * (~peaks2).astype(np.float64), kernel, mode='wrap') / (sum_mark + 1e-12)
    
    result_image = np.copy(image)
    result_image[peaks2] = tmp_image[peaks2]
    
    return result_image, peaks2, peaks3

def _detect_peaks(log_image, neighbour, mark, threshold):
    kernel = np.ones(neighbour)
    sum_mark = correlate(mark.astype(np.float64), kernel, mode='wrap')
    tmp_image = correlate(log_image * mark.astype(np.float64), kernel, mode='wrap') / (sum_mark + 1e-12)
    
    result_image = (log_image - tmp_image) / (tmp_image + 1e-12)
    return result_image >= threshold
