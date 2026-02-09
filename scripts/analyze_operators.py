from elasticsearch_dsl.query import Exists
from ray.data import read_datasource, Dataset
from ray_elasticsearch import ElasticsearchDatasource
from archive_query_log.orm import Serp

datasource = ElasticsearchDatasource(
    hosts=f"https://elasticsearch.srv.webis.de:9200",
    http_auth=("ajjxp", "jE7CjHPhXA3zAHgPxnzypsjLpfrjfET7"),
    index="aql_serps",
    schema=Serp,
    query=Exists(field="url_query"),
    meta_fields=[],
    source_fields=["url_query"],
)
ds: Dataset = read_datasource(datasource, override_num_blocks=100)
count = ds.count()
count_operator = ds.filter(lambda row: "site:" in row["url_query"]).count()
print(f"Found {count} SERPs and {count_operator} with operator.")
