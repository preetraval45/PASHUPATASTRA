# TrainingCourse

- **Date:** 2026-10-18
- **Phase:** Block G — RP-67
- **Commit(s):** this push

## What changed

/training is now a course. lib/training.ts holds six modules: lessons, a
real-life checklist, ATT&CK ids, a quiz and a drill link. components/course.tsx
has the Quiz, the Evaluation summary and ModuleStatus, with progress in
localStorage `pashu.training.v1`. Each module lives at
/training/[slug]. The scored drills remain below the course.
lib/training.test.ts checks answer indices, the ATT&CK id format and module
completeness.

## Why

The owner wants learners to learn cyber security they can apply in real life,
then be evaluated on it.

## Decisions made

- The facts follow their sources. NIST SP 800-61 Rev. 2 has four phases; Rev. 3
  (2025) is mentioned as aligning to CSF 2.0. ATT&CK ids were checked:
  T1566(.002), T1110(.003/.004), T1078, T1071.001, T1021.002, T1053.005, T1486.
- Progress stays client-side only, the same privacy stance as the drill token.
- No certificate is issued. A certificate from a demo site would claim more
  than it can back up.

## Next session should

- Consider server-side progress once the API is redeployed.
- More modules: ransomware response, cloud IAM, logging basics.
