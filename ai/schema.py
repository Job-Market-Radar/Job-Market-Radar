from typing import Literal

from pydantic import BaseModel, model_validator


class Extraction(BaseModel):
    skills: list[str]
    seniority: Literal["intern", "junior", "mid", "senior", "lead", "unknown"]
    remote: Literal["remote", "hybrid", "onsite", "unknown"]                 # ← blank 1
    salary_min: int | None
    salary_max: int | None
    currency: str | None                                                    # ← blank 2
    salary_period: Literal["hour", "month", "year", "unknown"] | None  
    
    @model_validator(mode="after")
    def fix_reversed_salary(self):
        """Some postings write ranges backwards ("$180k - 160k"): put the smaller number first."""
        if self.salary_min is not None and self.salary_max is not None and self.salary_min > self.salary_max:
            self.salary_min, self.salary_max = self.salary_max, self.salary_min
        return self     # ← blank 3
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