from django.db import transaction

from datetime import datetime
from .nbb_api import get_references, get_accounting_data
from .models import Company, AnnualAccount, FinancialRubric, Administrator, Person, Participation

@transaction.atomic
def import_financials(enterprise_number):
    company = Company.objects.get(number=enterprise_number)
    references = get_references(enterprise_number)
    
    incoming_refs = [
        {
            "reference": r.get('ReferenceNumber'),
            "end_date": r.get('ExerciseDates', {}).get('endDate')
        }
        for r in references
        if r.get('ReferenceNumber')
    ]

    incoming_ref_numbers = [ref["reference"] for ref in incoming_refs]

    existing_refs = set(
        AnnualAccount.objects.filter(reference__in=incoming_ref_numbers).values_list('reference', flat=True)
    )

    annual_accounts = [
        AnnualAccount(
            company=company,
            reference=ref["reference"],
            end_fiscal_year=ref["end_date"]
        )
        for ref in incoming_refs
        if ref["reference"] not in existing_refs
    ]

    AnnualAccount.objects.bulk_create(annual_accounts, batch_size=500)

    new_references = [acc.reference for acc in annual_accounts]
    
    account_lookup = {
        acc.reference: acc for acc in AnnualAccount.objects.filter(reference__in=new_references)
    }
    
    for ref in new_references:
        try:
            accounting_data = get_accounting_data(ref)
        except Exception:
            continue
        
        incoming_rubrics = [
            {
                "code": r.get('Code'),
                "value": r.get('Value')
            }
            for r in accounting_data.get('Rubrics', [])
            if r.get('Period') == 'N'
        ]
        
        rubrics = [
            FinancialRubric(
                code=rubric["code"],
                value=rubric["value"],
                annual_account=account_lookup[ref]
            )
            for rubric in incoming_rubrics
        ]
        
        FinancialRubric.objects.bulk_create(rubrics)
        
        incoming_administrators = []
        
        for legalEntity in accounting_data.get('Administrators', {}).get('LegalPersons', []):
            company_number = legalEntity.get('Entity', {}).get('Identifier')
            try:
                company_obj = Company.objects.get(number=company_number)
            except Company.DoesNotExist:
                continue

            incoming_administrators.append({
                "administering_company": company_obj,
                "representatives": legalEntity.get('Representatives'),
            })

        for naturalPerson in accounting_data.get('Administrators', {}).get('NaturalPersons', []):
            representatives = [naturalPerson.get('Person', {})]

            incoming_administrators.append({
                "administering_company": None,
                "representatives": representatives,
            })
            
        for item in incoming_administrators:
            reps_data = item["representatives"]
            reps = []

            if reps_data and len(reps_data) >= 1:
                print(reps_data)
                for rep in reps_data:
                    if not rep:
                        continue
                    person, _ = Person.objects.get_or_create(
                        first_name=rep.get("FirstName", "").strip(),
                        last_name=rep.get("LastName", "").strip()
                    )
                    reps.append(person)

            admin = Administrator.objects.create(
                administering_company=item["administering_company"],
                annual_account=account_lookup[ref],
            )

            admin.representatives.set(reps)
            
            incoming_participations = []
            
        for participation in accounting_data.get('ParticipatingInterests', []):
            company_number = participation.get('Entity', {}).get('Identifier')
            try:
                company_obj = Company.objects.get(number=company_number)
            except Company.DoesNotExist:
                continue
            
            for participating_interest in participation.get('ParticipatingInterestHeld', []):
                if participating_interest.get('Nature') == 'Aandelen':
                    percentage = participating_interest.get('PercentageDirectlyHeld')
                    stocks = participating_interest.get('Number')
                    if percentage and stocks:
                        incoming_participations.append({
                            "held_company": company_obj,
                            "percentage": percentage,
                            "stocks": stocks,
                            "annual_account": account_lookup[ref]
                        })
                        
        participation_objects = [
            Participation(**data) for data in incoming_participations
        ]

        Participation.objects.bulk_create(participation_objects)
        
        company.fin_fetch = datetime.now()
        company.save()