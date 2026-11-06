from app.services.frameworks import detect
from app.services.repository_inspector import safe_root_directory

def test_detect_vite():
    result=detect(["package.json","vite.config.ts","index.html"],{"devDependencies":{"vite":"*"},"scripts":{"build":"vite build"}})
    assert result["framework"]=="Vite" and result["output_directory"]=="dist"
def test_detect_react_vite_and_react():
    assert detect(["package.json"],{"dependencies":{"react":"*","vite":"*"}})["framework"]=="React + Vite"
    assert detect(["package.json"],{"dependencies":{"react":"*"}})["framework"]=="React"
def test_detect_python_fastapi_from_files():
    result=detect(["requirements.txt","main.py"],python_dependencies="fastapi==0.115")
    assert result["framework"]=="FastAPI"
def test_detect_django_and_other_common_frameworks():
    assert detect(["requirements.txt","manage.py"],python_dependencies="Django>=5")["framework"]=="Django"
    assert detect(["angular.json"])["framework"]=="Angular"
    assert detect(["composer.json"])["framework"]=="PHP"
    assert detect(["package.json"],{"dependencies":{"vue":"*","vite":"*"}})["framework"]=="Vue"
    assert detect(["index.php"])["framework"]=="PHP"
def test_detect_static_html():
    assert detect(["index.html","styles.css"])["framework"]=="Static HTML/CSS/JS"
def test_repository_root_is_repository_relative():
    assert safe_root_directory("./frontend/")=="frontend"
    for unsafe in ("../private","/absolute","C:/private","frontend/../private"):
        try:
            safe_root_directory(unsafe)
            assert False, f"unsafe root accepted: {unsafe}"
        except ValueError:
            pass
