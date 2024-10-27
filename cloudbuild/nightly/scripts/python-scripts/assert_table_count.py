import argparse
from collections.abc import Sequence

from absl import app
from google.cloud import bigquery
from google.cloud import storage
from absl import logging


def execute_query(bq_client, table_name, query):
    logging.info(f"Query: {query}")
    try:
        job = bq_client.query(query, location='US')
        rows = job.result()  # Start the job and wait for it to complete and get the result.
        for row in rows:
            return row['unique_key_count']
    except Exception as _:
        raise RuntimeError(f'Could not obtain the count of unique keys from table: {table_name}')


def get_unique_key_count(bq_client, project_name, dataset_name, table_name):
    table_id = f"{project_name}.{dataset_name}.{table_name}"
    query = (
        "SELECT COUNT(DISTINCT(unique_key)) as unique_key_count FROM `" + table_id + "`;"
    )
    return execute_query(bq_client, table_name, query)


def get_total_row_count(bq_client, project_name, dataset_name, table_name):
    table_id = f"{project_name}.{dataset_name}.{table_name}"
    query = (
        "SELECT COUNT(*) as unique_key_count FROM `" + table_id + "`;"
    )
    return execute_query(bq_client, table_name, query)


def get_total_row_count_unbounded(storage_client, source_gcs_uri):
    path_to_csv = source_gcs_uri + "fullSource.csv"
    bucket_name = path_to_csv.split("/")[2]
    # Extract the relevant components
    blob_path = '/'.join(path_to_csv.split('/')[3:])
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(blob_path)
    content = blob.download_as_string().decode('utf-8')
    row_count = len(content.splitlines())

    return row_count


def assert_total_row_count(bq_client, storage_client, project_name, dataset_name, source,
                           destination_table_name, mode, is_exactly_once):
    source_total_row_count = 0
    if mode == "unbounded":
        source_total_row_count = get_total_row_count_unbounded(storage_client, source)
    else:
        source_total_row_count = get_total_row_count(client, project_name, dataset_name,
                                                 source)
    logging.info(f"Total Row Count for Source Table {source}:"
                 f" {source_total_row_count}")

    destination_total_row_count = get_total_row_count(bq_client, project_name, dataset_name,
                                                      destination_table_name)
    logging.info(f"Total Row Count for Destination Table {destination_table_name}:"
                 f" {destination_total_row_count}")
    if is_exactly_once:
        if source_total_row_count != destination_total_row_count:
            raise AssertionError("Source and Destination Row counts do not match")
    else:
        if destination_total_row_count < source_total_row_count:
            raise AssertionError("Destination Row count is less than Source Row Count")


def assert_unique_key_count(bq_client, storage_client, project_name, dataset_name, source,
                            destination_table_name,
                            mode,
                            is_exactly_once):
    source_unique_key_count = 0
    if mode == "unbounded":
            source_unique_key_count = get_total_row_count_unbounded(storage_client, source)
    else:
            source_unique_key_count = get_unique_key_count(client, project_name, dataset_name,
                                                   source)
    logging.info(
        f"Unique Key Count for Source Table {source}: {source_unique_key_count}")
    destination_unique_key_count = get_unique_key_count(bq_client, project_name, dataset_name,
                                                        destination_table_name)
    logging.info(
        f"Unique Key Count for Destination Table {destination_table_name}:"
        f" {destination_unique_key_count}")

    if is_exactly_once:
        if source_unique_key_count != destination_unique_key_count:
            raise AssertionError("Source and Destination Key counts do not match!")
    else:
        if source_unique_key_count < destination_unique_key_count:
            raise AssertionError("Destination Row Key count is less than Source Key Count!")


def main(argv: Sequence[str]) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--project_name',
        dest='project_name',
        help='Project Id which contains the table to be read.',
        type=str,
        default='',
        required=True,
    )
    parser.add_argument(
        '--dataset_name',
        dest='dataset_name',
        help='Dataset Name which contains the table to be read.',
        type=str,
        default='',
        required=True,
    )
    parser.add_argument(
        '--source',
        dest='source',
        help='Table Name or GCS URI of the table which is source for write test.',
        type=str,
        default='',
        required=True,
    )

    parser.add_argument(
        '--destination_table_name',
        dest='destination_table_name',
        help='Table Name of the table which is destination for write test.',
        type=str,
        default='',
        required=True,
    )

    parser.add_argument(
        '--is_exactly_once',
        dest='is_exactly_once',
        help='Set the flag to True If "EXACTLY ONCE" mode is enabled.',
        action='store_true',
        default=False,
        required=False,
    )

    parser.add_argument(
            '--mode',
            dest='mode',
            help='Set the flag to True If "EXACTLY ONCE" mode is enabled.',
            action='store_true',
            default=False,
            required=False,
        )

    args = parser.parse_args(argv[1:])

    # Providing the values.
    project_name = args.project_name
    dataset_name = args.dataset_name
    source = args.source
    destination_table_name = args.destination_table_name
    is_exactly_once = args.is_exactly_once
    mode = args.mode

    bq_client = bigquery.Client(project=project_name)
    storage_client = storage.Client(project=project_name)
    assert_total_row_count(bq_client, storage_client, project_name, dataset_name, source,
                           destination_table_name, mode, is_exactly_once)

    assert_unique_key_count(bq_client, storage_client, project_name, dataset_name, source,
                            destination_table_name, mode, is_exactly_once)


if __name__ == '__main__':
    app.run(main)
