from pathlib import Path
from jinja2 import FileSystemLoader, Environment, StrictUndefined


PROMPTS_DIR = Path(__name__).parent 

env = Environment(
    loader=FileSystemLoader(searchpath=PROMPTS_DIR), 
    undefined=StrictUndefined, 
    trim_blocks=True, 
    lstrip_blocks=True
)

def render_template(template_name: str, context: dict) -> str: 
    template = env.get_template(name=template_name)
    return template.render(**context)