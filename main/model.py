import tensorflow as tf
import tensorflow.contrib.slim as slim
from config import cfg
from net.hrnet import HRNet
from tfflat.base import ModelDesc


class Model(ModelDesc):

    def head_net(self, blocks, is_training, trainable=True):

        msra_initializer = tf.contrib.layers.variance_scaling_initializer()

        out = slim.conv2d(blocks[0], cfg.num_kps, [1, 1],
                          trainable=trainable, weights_initializer=msra_initializer,
                          padding='SAME', normalizer_fn=None, activation_fn=None,
                          scope='out', data_format='NCHW')

        return out

    def render_gaussian_heatmap(self, coord, output_shape, sigma):

        x = [i for i in range(output_shape[1])]
        y = [i for i in range(output_shape[0])]
        xx, yy = tf.meshgrid(x, y)
        xx = tf.reshape(tf.to_float(xx), (1, *output_shape, 1))
        yy = tf.reshape(tf.to_float(yy), (1, *output_shape, 1))

        x = tf.floor(tf.reshape(coord[:, :, 0], [-1, 1, 1, cfg.num_kps]) / cfg.input_shape[1] * output_shape[1] + 0.5)
        y = tf.floor(tf.reshape(coord[:, :, 1], [-1, 1, 1, cfg.num_kps]) / cfg.input_shape[0] * output_shape[0] + 0.5)

        heatmap = tf.exp(-(((xx - x) / tf.to_float(sigma)) ** 2) / tf.to_float(2) - (
                ((yy - y) / tf.to_float(sigma)) ** 2) / tf.to_float(2))

        return heatmap * 255.

    def make_network(self, is_train):
        if is_train:
            image = tf.placeholder(tf.float32, shape=[cfg.batch_size, *cfg.input_shape, 3])
            target_coord = tf.placeholder(tf.float32, shape=[cfg.batch_size, cfg.num_kps, 2])
            valid = tf.placeholder(tf.float32, shape=[cfg.batch_size, cfg.num_kps])
            self.set_inputs(image, target_coord, valid)
        else:
            image = tf.placeholder(tf.float32, shape=[None, *cfg.input_shape, 3])
            self.set_inputs(image)

        with tf.variable_scope('HRNET'):
            image = tf.transpose(image, [0, 3, 1, 2])
            hrnet_fms = HRNet(cfg.hrnet_config, image, is_train)
            heatmap_outs = self.head_net(hrnet_fms, is_train)
            heatmap_outs = tf.transpose(image, [0, 2, 3, 1])

        if is_train:
            gt_heatmap = tf.stop_gradient(self.render_gaussian_heatmap(target_coord, cfg.output_shape, cfg.sigma))
            valid_mask = tf.reshape(valid, [cfg.batch_size, 1, 1, cfg.num_kps])
            loss = tf.reduce_mean(tf.square(heatmap_outs - gt_heatmap) * valid_mask)
            self.add_tower_summary('loss', loss)
            self.set_loss(loss)
        else:
            self.set_outputs(heatmap_outs)
