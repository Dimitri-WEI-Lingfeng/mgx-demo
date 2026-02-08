


framework_docker_images = {
    "nextjs": "mgx-dev-nextjs:latest",
}

def get_framework_docker_image(framework: str) -> str:
    image = framework_docker_images.get(framework, None)
    if not image:
        raise ValueError(f"Unsupported framework: {framework}")
    return image



def get_framework_docker_port(framework: str) -> int:
    if framework == "nextjs":
        return 3000
    elif framework == "fastapi-vite":
        return 8000
    else:
        raise ValueError(f"Unsupported framework: {framework}")