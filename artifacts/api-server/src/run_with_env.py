import os
import sys

# Set environment variables
os.environ['FALKORDB_HOST'] = 'r-6jissuruar.instance-keqdkat0a.hc-7up0crkyn.ap-south-1.aws.f2e0a955bb84.cloud'
os.environ['FALKORDB_PORT'] = '65332'
os.environ['FALKORDB_USERNAME'] = 'falkordb'
os.environ['FALKORDB_PASSWORD'] = 'whatif-graph-001'
os.environ['FALKORDB_SSL'] = 'true'
os.environ['FALKORDB_GRAPH_NAME'] = 'whatif_graph'
os.environ['PORT'] = '8888'

# Import and run the app
from main import app
import uvicorn

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8888"))
    uvicorn.run(app, host="0.0.0.0", port=port)
