FROM quay.io/jupyter/pyspark-notebook:latest

USER root

RUN apt-get update && apt-get install -y \
    curl \
    wget \
    git \
    vim \
    netcat-openbsd \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

USER ${NB_UID}

RUN pip install --no-cache-dir \
    xarray \
    zarr \
    gcsfs \
    s3fs \
    boto3 \
    pyarrow \
    pandas \
    numpy \
    pyyaml \
    python-dotenv \
    kafka-python \
    deltalake \
    tqdm \
    matplotlib