import os

import jsonpickle
import pandas as pd
from flask import Flask, flash, render_template, session, request, redirect, url_for
from werkzeug.utils import secure_filename

from configuration import const_types
from configuration import key
from configuration import paths
from controllers.data_summary import DataSummary
from controllers.data_univariate import DataUnivariate
from controllers.data_bivariate import DataBivariate
from model.dataset import DataSet
from model.datasets import DataSets

app = Flask(__name__)

# Path and upload information
app.config['UPLOAD_FOLDER'] = paths.UPLOAD_FOLDER
app.config['EXAMPLES_FOLDER'] = paths.EXAMPLES_FOLDER
app.secret_key = key.SECRET_KEY


@app.before_first_request
def getmenu():
    if not os.path.isfile(paths.DATASETS_JSON):
        dataset_info = []

        # Read in CSV
        datasets_csv = pd.read_csv(paths.DATASETS)

        # Get title, filename, id, and label for each data set and add it to the collection
        for i, row in datasets_csv.iterrows():
            dataset_title = row["Title"]
            dataset_filename = row["FileName"]
            dataset_id = row["ID"]
            dataset_label = row["Label"]
            dataset = DataSet(dataset_filename, dataset_title, dataset_id, dataset_label)
            dataset_info.append(dataset)

        # Save the collection as JSON and return it
        datasets = DataSets(dataset_info=dataset_info)
        datasets_json = jsonpickle.encode(datasets)

        # Save the serialized JSON to a file
        with open(paths.DATASETS_JSON, 'w') as file:
            file.write(datasets_json)
    else:
        with open(paths.DATASETS_JSON, 'r') as serialized_file:
            json_str = serialized_file.read()
            datasets_json = jsonpickle.decode(json_str)

    return datasets_json


def selecteddataset():
    data_file = None
    data_title = None
    data_id = None
    data_label = None
    data_uploaded = False

    # Check if the values are already in session
    if "data_file" in session:
        data_file = session["data_file"]
    if "data_title" in session:
        data_title = session["data_title"]
    if "data_id" in session:
        data_id = session["data_id"]
    if "data_label" in session:
        data_label = session["data_label"]
    if "data_file_uploaded" in session and session["data_file_uploaded"] == data_file:
        data_uploaded = True

    # Make sure that at least the file and title are populated, or else get it from the page
    if data_file is None or data_title is None:
        # Get the current selected values
        data_file = "iris.csv"
        data_title = "Iris"
        data_id = "ID"
        data_label = "Species"
        data_uploaded = False

        # Save values in session for future requests
        session["data_file"] = data_file
        session["data_title"] = data_title
        session["data_id"] = data_id
        session["data_label"] = data_label

    return [data_file, data_title, data_id, data_label, data_uploaded]


@app.route('/dataset_selection_changed', methods=['POST'])
def dataset_selection_changed():
    # Get the selected data set's name
    new_selection = str(request.form["data_set_field"])

    # Look up the Title, ID, Label (for existing data sets)
    datasets = pd.read_csv(paths.DATASETS)
    dataset = datasets.loc[datasets["FileName"] == new_selection]

    if dataset is not None:
        new_title = dataset["Title"].values[0]
        new_index = dataset["ID"].values[0]
        new_label = dataset["Label"].values[0]

        # Save the selection in session
        session["data_file"] = new_selection
        session["data_title"] = new_title
        session["data_id"] = new_index
        session["data_label"] = new_label

    # Redirect and reload the appropriate page
    if request.referrer is not None:
        return redirect(request.referrer)
    else:
        return redirect(url_for('index'))


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in const_types.ALLOWED_EXTENSIONS


@app.route('/upload', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        # Check if a file was passed into the request
        if 'file' not in request.files:
            flash('No file part')
            return redirect(request.url)

        # Get the uploaded file
        file = request.files['file']

        # Check if a file was not selected
        if file.filename == '':
            flash('No selected file')
            return redirect(request.url)

        # If the file was uploaded and is an allowed type, proceed with upload
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(paths.UPLOAD_FOLDER, filename)
            file.save(filepath)

            data_title = ""
            data_id = ""
            data_label = ""

            if "label" in request.form:
                data_title = request.form["title"]
            if "id" in request.form:
                data_id = request.form["id"]
            if "label" in request.form:
                data_label = request.form["label"]

            # Move the file and set metadata
            datasetuploaded(uploaded_file_path=str(filepath),
                            data_title=data_title,
                            data_id=data_id,
                            data_label=data_label)

            # Return to the summary page and show the new data set info
            return redirect(url_for('index'))
    else:
        dataset_options = getmenu()
        return render_template('upload.html', dataset_options=dataset_options)


def datasetuploaded(uploaded_file_path, data_title, data_id=None, data_label=None):
    # Create folder with graphs sub folder
    data_path = os.path.join(paths.UPLOAD_FOLDER, data_title)
    if not os.path.exists(data_path):
        os.makedirs(data_path)
        os.makedirs(os.path.join(data_path, "graphs"))

    # Move the uploaded file to this directory
    file_name = uploaded_file_path.split("/")[-1]
    os.rename(uploaded_file_path, str(data_path + "/" + file_name))

    # Update the list of options to select from
    session["data_file"] = file_name
    session["data_title"] = data_title
    session["data_id"] = data_id
    session["data_label"] = data_label

    # Set the uploaded one
    session["data_file_uploaded"] = file_name
    session["data_title_uploaded"] = data_title
    session["data_id_uploaded"] = data_id
    session["data_label_uploaded"] = data_label


def getuploadeddataset():
    data_file = None
    data_title = None
    data_id = None
    data_label = None

    if "data_file_uploaded" in session:
        data_file = session["data_file_uploaded"]
    if "data_title_uploaded" in session:
        data_title = session["data_title_uploaded"]
    if "data_id_uploaded" in session:
        data_id = session["data_id_uploaded"]
    if "data_label_uploaded" in session:
        data_label = session["data_label_uploaded"]

    if data_file is not None and data_title is not None:
        return [data_file, data_title, data_id, data_label, True]

    return None


@app.route('/')
@app.route('/index')
def index():
    # data_file, data_title, data_id, data_label = selecteddataset()
    selected_dataset = selecteddataset()
    dataset_options = getmenu()
    uploaded_dataset = getuploadeddataset()

    driver = DataSummary(selected_dataset)

    # Get the JSON for the summary data
    summary_json = driver.load_summary_json()
    error_msg = driver.get_error_msg()

    return render_template('index.html',
                           data=summary_json,
                           data_file=selected_dataset[0],
                           dataset_options=dataset_options,
                           uploaded_dataset=uploaded_dataset,
                           error_msg=error_msg)


@app.route('/univariate')
def univariate():
    selected_dataset = selecteddataset()
    dataset_options = getmenu()
    uploaded_dataset = getuploadeddataset()

    driver = DataUnivariate(selected_dataset)

    # Get the JSON for the summary data
    features_json = driver.load_features_json()
    error_msg = driver.get_error_msg()

    return render_template('univariate.html',
                           mydata=features_json,
                           data_file=selected_dataset[0],
                           dataset_options=dataset_options,
                           uploaded_dataset=uploaded_dataset,
                           error_msg=error_msg)


@app.route('/bivariate')
def bivariate():
    selected_dataset = selecteddataset()
    dataset_options = getmenu()
    uploaded_dataset = getuploadeddataset()

    driver = DataBivariate(selected_dataset)

    # Get the JSON for the summary data
    interactions_json = driver.load_interactions_json()
    error_msg = driver.get_error_msg()

    return render_template('bivariate.html',
                           data=interactions_json,
                           data_file=selected_dataset[0],
                           dataset_options=dataset_options,
                           uploaded_dataset=uploaded_dataset,
                           error_msg=error_msg)
