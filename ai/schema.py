from typing import Literal

from pydantic import BaseModel


class Extraction(BaseModel):
    """The form the AI must fill in for each job posting."""

    skills: list[str]
    seniority: Literal["intern", "junior", "mid", "senior", "lead", "unknown"]
    remote: Literal["remote", "hybrid", "onsite", "unknown"]                 # ← blank 1
    salary_min: int | None
    salary_max: int | None
    currency: str | None                                                    # ← blank 2
    salary_period: Literal["hour", "month", "year", "unknown"] | None       # ← blank 3
class CvSkills(BaseModel):
    """The form the AI fills in for a CV: just the skills."""

    skills: list[str]

if __name__ == "__main__":
    good = Extraction(
        skills=["python"], seniority="senior", remote="remote",
        salary_min=170000, salary_max=200000, currency="USD", salary_period="year",
    )
    print("good one passed:", good)

    bad = Extraction(
        skills=["python"], seniority="Senior", remote="remote",
        salary_min="170k", salary_max=None, currency=None, salary_period=None,
    )