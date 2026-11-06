from app.services.frameworks import detect

def test_detect_vite():
    result=detect(["package.json","vite.config.ts","index.html"],{"devDependencies":{"vite":"*"},"scripts":{"build":"vite build"}})
    assert result["framework"]=="Vite" and result["output_directory"]=="dist"
def test_detect_python_fastapi_from_files():
    result=detect(["requirements.txt","main.py"])
    assert result["framework"]=="Python"
def test_detect_static_html():
    assert detect(["index.html","styles.css"])["framework"]=="Static HTML"
