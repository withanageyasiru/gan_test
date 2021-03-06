# coding=utf-8
import os
os.environ["TF_FORCE_GPU_ALLOW_GROWTH"] = "true"

import numpy as np
from keras.models import Model
from keras.layers import Input, Lambda
from keras import backend as K
from keras.optimizers import Adam
from keras.preprocessing.image import ImageDataGenerator
from utils import sample
from models import load_model


if not os.path.exists('samples'):
    os.mkdir('samples')


img_dim = 64
z_dim = 100
total_iter = 1000000
batch_size = 64
iters_per_sample = 100 # 采样频率


img_dir = '/media/gt/_dde_data/Datasets/CASIA-maxpy-clean'
#img_dir = '../../datasets/CASIA-maxpy-clean'

# 数据生成器
img_datagen = ImageDataGenerator(
    preprocessing_function=lambda x: x.astype(np.float32) / 255 * 2 - 1,
    zoom_range=0.0 # 缩放， 0.5 放大
)
img_generator = img_datagen.flow_from_directory(
    img_dir,
    target_size=(img_dim, img_dim),
    batch_size=batch_size,
    class_mode=None # 只生成图片，不生成标签
)


# 载入基本模型： 判别器，生成器
d_model, g_model = load_model(img_dim, z_dim, use_bias=False)
d_model.summary()
g_model.summary()


# 整合模型（训练判别器）
x_in = Input(shape=(img_dim, img_dim, 3))
z_in = Input(shape=(z_dim, ))
g_model.trainable = False


def interpolating(x):
    u = K.random_uniform((K.shape(x[0])[0],) + (1,) * (K.ndim(x[0]) - 1))
    return x[0] * u + x[1] * (1 - u)

x_fake = g_model(z_in)
x_inter = Lambda(interpolating)([x_in, x_fake])
x_real_score = d_model(x_in)
x_fake_score = d_model(x_fake)
x_inter_score = d_model(x_inter)

grads = K.gradients(x_inter_score, [x_inter])[0]
grad_norms = K.sqrt(K.sum(grads**2, list(range(1, K.ndim(grads)))) + 1e-9)

d_train_model = Model([x_in, z_in],
                      [x_real_score, x_fake_score, x_inter_score])

d_loss = K.mean(- (x_real_score - x_fake_score)) + 10 * K.mean((grad_norms - 1)**2)
d_train_model.add_loss(d_loss)
d_train_model.compile(optimizer=Adam(2e-4, 0.5))


# 整合模型（训练生成器）
g_model.trainable = True
d_model.trainable = False
x_fake_score = d_model(g_model(z_in))

g_train_model = Model(z_in, x_fake_score)
g_train_model.add_loss(K.mean(- x_fake_score))
g_train_model.compile(optimizer=Adam(2e-4, 0.5))


# 检查模型结构
d_train_model.summary()
g_train_model.summary()


for i in range(total_iter):
    for j in range(5):
        next_batch = next(img_generator)
        z_sample = np.random.randn(len(next_batch), z_dim)       
        d_loss = d_train_model.train_on_batch(
            [next_batch, z_sample], None)
    for j in range(1):
        z_sample = np.random.randn(batch_size, z_dim)
        g_loss = g_train_model.train_on_batch(z_sample, None)
    if i % 10 == 0:
        print('iter: %s, d_loss: %s, g_loss: %s' % (i, d_loss, g_loss))
    if i % iters_per_sample == 0:
        sample('samples/test_%s.png' % i, g_model, img_dim, z_dim)
        g_train_model.save_weights('./g_train_model.weights')
