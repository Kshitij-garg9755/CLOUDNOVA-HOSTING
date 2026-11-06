def detect(files:list[str],package:dict|None=None)->dict:
    names={x.lower().split("/")[-1] for x in files};paths={x.lower() for x in files};deps={**(package or {}).get("dependencies",{}),**(package or {}).get("devDependencies",{})};scripts=(package or {}).get("scripts",{})
    if "next.config.js" in names or "next.config.mjs" in names or "next" in deps:return {"framework":"Next.js","install_command":"npm ci","build_command":"npm run build","output_directory":"out","runtime_version":"20","app_port":3000}
    if "vite.config.ts" in names or "vite.config.js" in names or "vite" in deps:return {"framework":"Vite","install_command":"npm ci","build_command":"npm run build","output_directory":"dist","runtime_version":"20"}
    if "angular.json" in names or "@angular/core" in deps:return {"framework":"Angular","install_command":"npm ci","build_command":"npm run build","output_directory":"dist","runtime_version":"20"}
    if "vue.config.js" in names or "vue" in deps:return {"framework":"Vue","install_command":"npm ci","build_command":"npm run build","output_directory":"dist","runtime_version":"20"}
    if "package.json" in names:return {"framework":"Node.js","install_command":"npm ci","build_command":"npm run build" if "build" in scripts else None,"start_command":"npm start" if "start" in scripts else None,"runtime_version":"20","app_port":3000}
    if "pyproject.toml" in names or "requirements.txt" in names:
        fast="fastapi" in " ".join(paths);return {"framework":"FastAPI" if fast else "Python","install_command":"pip install -r requirements.txt" if "requirements.txt" in names else "pip install .","start_command":"uvicorn main:app --host 0.0.0.0 --port $PORT" if fast else None,"runtime_version":"3.11","app_port":8000}
    if "composer.json" in names:return {"framework":"PHP/Laravel" if "artisan" in names else "PHP","install_command":"composer install --no-dev","runtime_version":"8.3","app_port":8080}
    if "pom.xml" in names:return {"framework":"Java/Spring Boot","build_command":"./mvnw package -DskipTests","start_command":"java -jar target/*.jar","runtime_version":"21","app_port":8080}
    if "build.gradle" in names or "build.gradle.kts" in names:return {"framework":"Java/Gradle","build_command":"./gradlew build -x test","start_command":"java -jar build/libs/*.jar","runtime_version":"21","app_port":8080}
    if "dockerfile" in names:return {"framework":"Docker","build_command":"docker build","app_port":8080}
    if "index.html" in names:return {"framework":"Static HTML","output_directory":".","install_command":None,"build_command":None}
    return {"framework":"Unknown","install_command":None,"build_command":None,"output_directory":None}
