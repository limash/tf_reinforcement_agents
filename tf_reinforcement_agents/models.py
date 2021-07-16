# move all imports inside functions to use ray.remote multitasking

def mlp_layer(x):
    from tensorflow import keras
    import tensorflow.keras.layers as layers

    # initializer = "he_normal"
    # x = layers.Dense(512, kernel_initializer=initializer, activation='relu')(x)

    initializer = keras.initializers.VarianceScaling(
        scale=2.0, mode='fan_in', distribution='truncated_normal')

    x = layers.Dense(1000, kernel_initializer=initializer,
                     kernel_regularizer=keras.regularizers.l2(0.01),
                     use_bias=False)(x)
    x = layers.BatchNormalization()(x)
    x = layers.ELU()(x)
    # x = layers.ReLU()(x)

    x = layers.Dense(1000, kernel_initializer=initializer,
                     kernel_regularizer=keras.regularizers.l2(0.01),
                     use_bias=False)(x)
    x = layers.BatchNormalization()(x)
    x = layers.ELU()(x)
    # x = layers.ReLU()(x)

    return x


def conv_layer(x):
    import tensorflow.keras.layers as layers
    from tensorflow import keras

    # x = layers.Conv2D(32, 8, kernel_initializer=initializer, strides=4, activation='relu')(x)
    # x = layers.Conv2D(64, 4, kernel_initializer=initializer, strides=2, activation='relu')(x)
    # x = layers.Conv2D(64, 3, kernel_initializer=initializer, strides=1, activation='relu')(x)

    initializer = keras.initializers.VarianceScaling(
        scale=2.0, mode='fan_in', distribution='truncated_normal')

    x = layers.Conv2D(64, 5, kernel_initializer=initializer, padding='same')(x)
    x = layers.BatchNormalization()(x)
    x = layers.ELU()(x)
    x = layers.Conv2D(64, 3, kernel_initializer=initializer, padding='valid')(x)
    x = layers.BatchNormalization()(x)
    x = layers.ELU()(x)
    x = layers.Conv2D(128, 3, kernel_initializer=initializer, padding='valid')(x)
    x = layers.BatchNormalization()(x)
    x = layers.ELU()(x)
    x = layers.Conv2D(128, 3, kernel_initializer=initializer, padding='valid')(x)
    x = layers.BatchNormalization()(x)
    x = layers.ELU()(x)

    return x


def stem(input_shape, initializer=None):
    import tensorflow as tf
    from tensorflow import keras
    import tensorflow.keras.layers as layers

    feature_maps_shape, scalar_features_shape = input_shape
    # create inputs
    feature_maps_input = layers.Input(shape=feature_maps_shape, name="feature_maps", dtype=tf.uint8)
    scalar_feature_input = layers.Input(shape=scalar_features_shape, name="scalar_features", dtype=tf.uint8)
    inputs = [feature_maps_input, scalar_feature_input]
    # feature maps
    features_preprocessing_layer = keras.layers.Lambda(lambda obs: tf.cast(obs, tf.float32))
    features = features_preprocessing_layer(feature_maps_input)
    conv_output = conv_layer(features)
    # conv_output = handy_rl_resnet(features, initializer)
    # processing
    # h_head_filtered = keras.layers.Multiply()([tf.expand_dims(features[:, :, :, 0], -1), conv_output])
    # conv_proc_output = keras.layers.Conv2D(32, 1, kernel_initializer=initializer)(conv_output)
    flatten_conv_output = layers.Flatten()(conv_output)
    # x = layers.Dense(100, kernel_initializer=initializer,
    #                  kernel_regularizer=keras.regularizers.l2(0.01),
    #                  use_bias=False)(flatten_conv_output)
    # x = layers.BatchNormalization()(x)
    # # x = layers.ELU()(x)
    # x = layers.ReLU()(x)

    # concatenate inputs
    scalars_preprocessing_layer = keras.layers.Lambda(lambda obs: tf.cast(obs, tf.float32))
    scalars = scalars_preprocessing_layer(scalar_feature_input)
    # x = layers.Concatenate(axis=-1)([x, scalars])
    x = layers.Concatenate(axis=-1)([flatten_conv_output, scalars])
    # mlp
    x = mlp_layer(x)
    # x = layers.Dense(100, kernel_initializer=initializer,
    #                  kernel_regularizer=keras.regularizers.l2(0.01),
    #                  use_bias=False)(x)
    # x = layers.BatchNormalization()(x)
    # # x = layers.ELU()(x)
    # x = layers.ReLU()(x)

    return inputs, x


def get_dqn(input_shape, n_outputs, is_duel=False):
    import tensorflow as tf
    from tensorflow import keras
    import tensorflow.keras.layers as layers

    inputs, x = stem(input_shape)
    # this initialization in the last layer decreases variance in the last layer
    initializer = keras.initializers.random_uniform(minval=-0.03, maxval=0.03)
    # dueling
    if is_duel:
        state_values = layers.Dense(1, kernel_initializer=initializer)(x)
        raw_advantages = layers.Dense(n_outputs, kernel_initializer=initializer)(x)
        # advantages = raw_advantages - tf.reduce_max(raw_advantages, axis=1, keepdims=True)
        advantages = raw_advantages - tf.reduce_mean(raw_advantages, axis=1, keepdims=True)
        outputs = state_values + advantages
    else:
        outputs = layers.Dense(n_outputs, kernel_initializer=initializer)(x)

    model = keras.Model(inputs=[inputs], outputs=[outputs])

    return model


def get_actor_critic(input_shape, n_outputs):
    from tensorflow import keras
    import tensorflow.keras.layers as layers

    initializer_glorot = keras.initializers.GlorotUniform()
    initializer_random = keras.initializers.random_uniform(minval=-0.03, maxval=0.03)
    bias_initializer = keras.initializers.Constant(-0.2)
    # initializer_vs = keras.initializers.VarianceScaling(
    #     scale=2.0, mode='fan_in', distribution='truncated_normal')

    inputs, x = stem(input_shape, initializer_glorot)

    policy_logits = layers.Dense(n_outputs,
                                 kernel_initializer=initializer_glorot)(x)  # are not normalized logs
    # baseline = layers.Dense(1, kernel_initializer=initializer_random, bias_initializer=bias_initializer,
    #                         activation=keras.activations.tanh)(x)
    # baseline = layers.Dense(1, kernel_initializer=initializer_random, bias_initializer=bias_initializer)(x)
    baseline = layers.Dense(1, kernel_initializer=initializer_random)(x)

    model = keras.Model(inputs=[inputs], outputs=[policy_logits, baseline])

    return model


def get_actor_critic2():
    import tensorflow as tf
    from tensorflow import keras

    class ResidualUnit(keras.layers.Layer):
        def __init__(self, filters, initializer, activation, circular_pad, **kwargs):
            super().__init__(**kwargs)

            self._circular_pad = circular_pad
            self.activation = keras.activations.get(activation)
            self.main_layers = [
                keras.layers.Conv2D(filters, 3, kernel_initializer=initializer, use_bias=False),
                keras.layers.BatchNormalization()
            ]

        def call(self, inputs, **kwargs):
            x = inputs
            if self._circular_pad:
                x = tf.concat([x[:, -1:, :, :], x, x[:, :1, :, :]], 1)
                x = tf.concat([x[:, :, -1:, :], x, x[:, :, :1, :]], 2)

            for layer in self.main_layers:
                x = layer(x)
            return self.activation(inputs + x)

        def compute_output_shape(self, batch_input_shape):
            if self._circular_pad:
                return batch_input_shape
            else:
                batch, x, y, layers = batch_input_shape
                return [batch, x - 2, y - 2, layers]

    class ResidualModel(keras.Model):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)

            padding_layers = 12
            no_padding_layers = 3
            filters = 32

            initializer = keras.initializers.VarianceScaling(scale=2.0, mode='fan_in', distribution='truncated_normal')
            initializer_random = keras.initializers.random_uniform(minval=-0.03, maxval=0.03)
            activation = 'elu'

            self._pad_residuals = [ResidualUnit(filters, initializer, activation, True) for _ in range(padding_layers)]
            self._residuals = [ResidualUnit(filters, initializer, activation, False) for _ in range(no_padding_layers)]
            self._all_residuals = self._pad_residuals + self._residuals
            self._flatten = keras.layers.Flatten()
            self._dense_block = [keras.layers.Dense(1000, kernel_initializer=initializer,
                                                    kernel_regularizer=keras.regularizers.l2(0.01),
                                                    use_bias=False),
                                 keras.layers.BatchNormalization(),
                                 keras.layers.ELU()]
            self._logits_block = keras.layers.Dense(4, kernel_initializer=initializer_random)
            self._baseline_block = keras.layers.Dense(1, kernel_initializer=initializer_random)

        def call(self, inputs, training=None, mask=None):
            maps, scalars = inputs
            maps = tf.cast(maps, tf.float32)
            scalars = tf.cast(scalars, tf.float32)

            x = maps
            for layer in self._all_residuals:
                x = layer(x)
            x = self._flatten(x)

            z = tf.concat([x, scalars], axis=-1)
            for layer in self._dense_block * 2:
                z = layer(z)

            policy_logits = self._logits_block(z)
            baseline = self._baseline_block(z)

            return policy_logits, baseline

        def get_config(self):
            pass

    return ResidualModel()
