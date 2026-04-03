ARG SPARK_BASE_IMAGE=apache/spark:3.5.1-java17-python3
FROM ${SPARK_BASE_IMAGE}

ARG DELTA_VERSION=3.1.0
ARG HADOOP_AWS_VERSION=3.3.4
ARG AWS_SDK_BUNDLE_VERSION=1.12.262
ARG SPARK_KAFKA_VERSION=3.5.1
ARG KAFKA_CLIENTS_VERSION=3.5.1
ARG COMMONS_POOL2_VERSION=2.11.1

USER root

RUN apt-get update && apt-get install -y --no-install-recommends curl python3-pip procps && \
    rm -rf /var/lib/apt/lists/* && \
    pip3 install --no-cache-dir delta-spark==${DELTA_VERSION} boto3 minio kafka-python pyarrow pandas numpy scikit-learn mlflow && \
    mkdir -p /opt/spark/jars-extra && \
    curl -fsSL -o /opt/spark/jars-extra/delta-spark_${DELTA_VERSION}.jar https://repo1.maven.org/maven2/io/delta/delta-spark_2.12/${DELTA_VERSION}/delta-spark_2.12-${DELTA_VERSION}.jar && \
    curl -fsSL -o /opt/spark/jars-extra/delta-storage_${DELTA_VERSION}.jar https://repo1.maven.org/maven2/io/delta/delta-storage/${DELTA_VERSION}/delta-storage-${DELTA_VERSION}.jar && \
    curl -fsSL -o /opt/spark/jars-extra/hadoop-aws-${HADOOP_AWS_VERSION}.jar https://repo1.maven.org/maven2/org/apache/hadoop/hadoop-aws/${HADOOP_AWS_VERSION}/hadoop-aws-${HADOOP_AWS_VERSION}.jar && \
    curl -fsSL -o /opt/spark/jars-extra/aws-java-sdk-bundle-${AWS_SDK_BUNDLE_VERSION}.jar https://repo1.maven.org/maven2/com/amazonaws/aws-java-sdk-bundle/${AWS_SDK_BUNDLE_VERSION}/aws-java-sdk-bundle-${AWS_SDK_BUNDLE_VERSION}.jar && \
    curl -fsSL -o /opt/spark/jars-extra/spark-sql-kafka-0-10_2.12-${SPARK_KAFKA_VERSION}.jar https://repo1.maven.org/maven2/org/apache/spark/spark-sql-kafka-0-10_2.12/${SPARK_KAFKA_VERSION}/spark-sql-kafka-0-10_2.12-${SPARK_KAFKA_VERSION}.jar && \
    curl -fsSL -o /opt/spark/jars-extra/spark-token-provider-kafka-0-10_2.12-${SPARK_KAFKA_VERSION}.jar https://repo1.maven.org/maven2/org/apache/spark/spark-token-provider-kafka-0-10_2.12/${SPARK_KAFKA_VERSION}/spark-token-provider-kafka-0-10_2.12-${SPARK_KAFKA_VERSION}.jar && \
    curl -fsSL -o /opt/spark/jars-extra/kafka-clients-${KAFKA_CLIENTS_VERSION}.jar https://repo1.maven.org/maven2/org/apache/kafka/kafka-clients/${KAFKA_CLIENTS_VERSION}/kafka-clients-${KAFKA_CLIENTS_VERSION}.jar && \
    curl -fsSL -o /opt/spark/jars-extra/commons-pool2-${COMMONS_POOL2_VERSION}.jar https://repo1.maven.org/maven2/org/apache/commons/commons-pool2/${COMMONS_POOL2_VERSION}/commons-pool2-${COMMONS_POOL2_VERSION}.jar && \
    cp /opt/spark/jars-extra/*.jar /opt/spark/jars/

COPY entrypoint.sh /opt/entrypoint.sh
RUN chmod +x /opt/entrypoint.sh

WORKDIR /workspace
ENTRYPOINT ["/opt/entrypoint.sh"]
