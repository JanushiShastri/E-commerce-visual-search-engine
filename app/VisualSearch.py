import io
import numpy as np
from sklearn.neighbors import NearestNeighbors
import sqlite3
from tensorflow.python.keras.applications.vgg19 import preprocess_input as PP
from tensorflow.python.keras.preprocessing import image
from app import app
import tensorflow as tf

import os, sys, inspect

currentdir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parentdir = os.path.dirname(currentdir)
sys.path.insert(0, parentdir)


# adapters to store and retrieve numpy arrays in sqlite databases...
def adapt_array(arr):
    out = io.BytesIO()
    np.save(out, arr)
    out.seek(0)
    return sqlite3.Binary(out.read())


def convert_array(text):
    out = io.BytesIO(text)
    out.seek(0)
    return np.load(out)


sqlite3.register_adapter(np.ndarray, adapt_array)
sqlite3.register_converter("array", convert_array)


class VisualSearch():

    def __init__(self, dataset):
        self.dataset = dataset
        self.model = None

    # method to load VGG19 model
    def _load_model(self, model=app.config["MODEL_NAME"]):
        if model == 'VGG':
            # load VGG model
            print("Loading VGG 19 pre-trained model...")
            self.VGG_model = tf.keras.models.load_model(app.config["MODEL_PATH"])

    # method to load features of each item
    def _load_features(self, model=app.config["MODEL_NAME"], remove_not_white=False):
        # connect to the database
        conn = sqlite3.connect(app.config["DB_PATH"], detect_types=sqlite3.PARSE_DECLTYPES)
        cur = conn.cursor()

        # extract the features
        if remove_not_white:
            cur.execute('SELECT img_id, item_id, features_' + model + ' FROM features_' + str(self.dataset) + ' WHERE active = ? AND transformation = ? AND white_background = ?',(1, '000', 1))
        else:
            cur.execute('SELECT img_id, item_id, features_' + model + ' FROM features_' + str(self.dataset) + ' WHERE active = ? AND transformation = ?',(1, '000'))

        data = cur.fetchall()
        self.features = [i[2] for i in data]
        self.items = [i[1] for i in data]
        self.images = [i[0].split(',000')[0] for i in data]

        conn.close()

    # method to fit the knn model
    def _fit_kNN(self, algorithm='brute', metric='cosine'):
        # fit kNN model
        X = np.array(self.features)
        self.kNN = NearestNeighbors(n_neighbors=app.config["NO_OF_SIMILAR_IMAGES"], algorithm=algorithm, metric=metric).fit(X)

    # main method - identify most similar items
    def run(self, path_image, model=app.config["MODEL_NAME"], algorithm='brute', metric='cosine', nb_imgs=100, remove_not_white=False):

        self.path_to_img = path_image

        # load the model
        self._load_model(model=model)

        # load the features
        self._load_features(model=model,remove_not_white=remove_not_white)

        # fit the kNN model
        self._fit_kNN(algorithm=algorithm, metric=metric)

        # calculate the features of the images
        if model == 'VGG':
            img = image.load_img(path_image, target_size=(224, 224))
            img = image.img_to_array(img)  # convert to array
            img = np.expand_dims(img, axis=0)
            img = PP(img)
            self.img_features = [self.VGG_model.predict(img).flatten()]
            tf.keras.backend.clear_session()

            # find most similar images in the dataset
        _, self.NN = self.kNN.kneighbors(self.img_features)

        # identify most similar items
        self.similar_items = [self.items[i] for i in self.NN[0]][:nb_imgs]
        self.similar_images = [self.images[i] for i in self.NN[0]][:nb_imgs]

    def similar_items_path(self):

        path_to_similar_items = []
        for i in range(len(self.similar_images)):
            if self.similar_items[i] not in self.similar_items[:i]:  # remove duplicate items
                #path = os.path.join(app.config["DATASET_IMAGES_PATH"], self.similar_images[i])
                path = self.similar_images[i]
                path_to_similar_items.append(path)
        return path_to_similar_items



