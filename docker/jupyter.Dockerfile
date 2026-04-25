# Pull S3A JARs from the bitnami Spark image so the driver classpath matches workers
FROM bitnamilegacy/spark:4.0.0 AS spark-jars

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
    pyspark==4.0.0 \
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
    matplotlib \
    mlflow \
    scikit-learn

# Copy S3A JARs from bitnami Spark into PySpark jars so the driver can talk to MinIO
USER root
COPY --from=spark-jars /opt/bitnami/spark/jars/hadoop-aws-3.3.4.jar \
     /opt/conda/lib/python3.13/site-packages/pyspark/jars/hadoop-aws-3.3.4.jar
COPY --from=spark-jars /opt/bitnami/spark/jars/aws-java-sdk-bundle-1.12.262.jar \
     /opt/conda/lib/python3.13/site-packages/pyspark/jars/aws-java-sdk-bundle-1.12.262.jar
USER ${NB_UID}