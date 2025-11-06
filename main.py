from fastapi import FastAPI
from scrape_func import scrape_inventory  # move that function there

app = FastAPI()

@app.get("/inventory/{ign}")
def get_inventory(ign: str):
    result = scrape_inventory(ign)
    return result

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)