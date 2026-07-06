from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Tutor, TutorSource, TutorSourceType


DEMO_TUTORS = [
    {
        "name": "Tutor Copa do Mundo FIFA",
        "description": "Especialista demonstrativo em Copas do Mundo FIFA.",
        "system_prompt": (
            "Voce e um tutor especialista em Copas do Mundo FIFA. "
            "Use as fontes cadastradas para responder com precisao e contexto historico."
        ),
        "sources": [
            {
                "name": "Wikipedia - Copa do Mundo FIFA",
                "type": TutorSourceType.URL,
                "location": "https://pt.wikipedia.org/wiki/Copa_do_Mundo_FIFA",
            },
        ],
    },
    {
        "name": "Tutor Python",
        "description": "Especialista demonstrativo em Python.",
        "system_prompt": (
            "Voce e um tutor especialista em Python. "
            "Priorize explicacoes didaticas, exemplos praticos e referencias da documentacao oficial."
        ),
        "sources": [
            {
                "name": "Python docs - pathlib",
                "type": TutorSourceType.URL,
                "location": "https://docs.python.org/3/library/pathlib.html",
            },
            {
                "name": "Python docs - built-in functions",
                "type": TutorSourceType.URL,
                "location": "https://docs.python.org/3/library/functions.html",
            },
            {
                "name": "Python tutorial - classes",
                "type": TutorSourceType.URL,
                "location": "https://docs.python.org/3/tutorial/classes.html",
            },
        ],
    },
    {
        "name": "Tutor Revolucao Francesa",
        "description": "Especialista demonstrativo sobre a Revolucao Francesa.",
        "system_prompt": (
            "Voce e um tutor especialista sobre a Revolucao Francesa. "
            "Explique causas, eventos, personagens e consequencias de forma clara."
        ),
        "sources": [
            {
                "name": "Wikipedia - Revolucao Francesa",
                "type": TutorSourceType.URL,
                "location": "https://pt.wikipedia.org/wiki/Revolu%C3%A7%C3%A3o_Francesa",
            },
        ],
    },
]


def seed_demo_tutors(db: Session) -> None:
    for demo_tutor in DEMO_TUTORS:
        tutor = db.scalar(select(Tutor).where(Tutor.name == demo_tutor["name"]))

        if tutor is None:
            tutor = Tutor(
                name=demo_tutor["name"],
                description=demo_tutor["description"],
                system_prompt=demo_tutor["system_prompt"],
            )
            db.add(tutor)
            db.flush()

        existing_source_locations = {source.location for source in tutor.sources}
        for source_data in demo_tutor["sources"]:
            if source_data["location"] in existing_source_locations:
                continue

            db.add(TutorSource(tutor=tutor, **source_data))

    db.commit()
