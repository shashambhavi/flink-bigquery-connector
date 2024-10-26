#!/bin/bash

# Copyright 2022 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the 'License');
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#            http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an 'AS IS' BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
PROPERTIES=$1
timestamp=$2
UNBOUNDED_JOB_SINK_PARALLELISM=$3
IS_SQL=$4

# Copy Source File to a temp directory
gcloud storage cp "$GCS_SOURCE_URI"source.csv "$GCS_SOURCE_URI"temp/"$timestamp"/"$IS_SQL"/source.csv
# Set the GCS bucket source to above copy for using in this test.
GCS_SOURCE_URI="$GCS_SOURCE_URI"temp/"$timestamp"/"$IS_SQL"/source.csv
# Lifecycle policy already set, no need of this command

# Modify the destination table name for all tests.
DESTINATION_TABLE_NAME="$DESTINATION_TABLE_NAME"_"$timestamp"
if [ "$IS_SQL" == True ]
  then
    echo "SQL Mode is Enabled!"
    DESTINATION_TABLE_NAME="$DESTINATION_TABLE_NAME"-"$IS_SQL"
fi
# Create the destination table from the source table schema.
python3 cloudbuild/nightly/scripts/python-scripts/create_unbounded_sink_table.py -- --project_name "$PROJECT_NAME" --dataset_name "$DATASET_NAME" --destination_table_name "$DESTINATION_TABLE_NAME"
# Set the expiration time to 1 hour.
bq update --expiration 3600 "$DATASET_NAME"."$DESTINATION_TABLE_NAME"

# Running this job async to make sure it exits so that dynamic data can be added
gcloud dataproc jobs submit flink --id "$JOB_ID" --jar="$GCS_JAR_LOCATION" --cluster="$CLUSTER_NAME" --region="$REGION" --properties="$PROPERTIES" --async -- --gcp-source-project "$PROJECT_NAME" --gcs-source-bucket-uri "$GCS_SOURCE_URI" --mode unbounded --file-discovery-interval "$FILE_DISCOVERY_INTERVAL" --gcp-dest-project "$PROJECT_NAME" --bq-dest-dataset "$DATASET_NAME" --bq-dest-table "$DESTINATION_TABLE_NAME" --sink-parallelism "$UNBOUNDED_JOB_SINK_PARALLELISM" --is-sql "$IS_SQL"

#---------------------The script should be changed here----------------------------------------------------
# Dynamically adding the data. This is timed 2.5 min wait for read and 5 min refresh time.
python3 cloudbuild/nightly/scripts/python-scripts/insert_dynamic_files.py -- --project_name "$PROJECT_NAME" --gcs_source_uri "$GCS_SOURCE_URI" --refresh_interval "$FILE_DISCOVERY_INTERVAL" --is_write_test

# Now the Dataproc job will automatically succeed after stipulated time (18 minutes hardcoded).
# we wait for it to succeed or finish.
gcloud dataproc jobs wait "$JOB_ID" --region "$REGION" --project "$PROJECT_NAME"

