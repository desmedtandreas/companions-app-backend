from django.db import transaction

from .nbb_api import get_references, get_accounting_data
from .utils import parse_enterprise_number, parse_enterprise_number_dotted, resolve_label
from .models import Company, AnnualAccount, FinancialRubric, Administrator, Person

@transaction.atomic
def import_financials(enterprise_number):
    enterprise_number = parse_enterprise_number(enterprise_number)
    company = Company.objects.get(number=parse_enterprise_number_dotted(enterprise_number))
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
            company_obj, _ = Company.objects.get_or_create(number=parse_enterprise_number_dotted(company_number))

            incoming_administrators.append({
                "administering_company": company_obj,
                "representatives": legalEntity.get('Representatives'),
                "mandate": resolve_label(
                    legalEntity.get('Mandates', [{}])[0].get('FunctionMandate'), 'function'
                ) or 'Bestuurder'
            })

        for naturalPerson in accounting_data.get('Administrators', {}).get('NaturalPersons', []):
            incoming_administrators.append({
                "administering_company": None,
                "representatives": [naturalPerson.get('Person')],
                "mandate": resolve_label(
                    naturalPerson.get('Mandates', [{}])[0].get('FunctionMandate'), 'function'
                ) or 'Bestuurder'
            })
            
        for item in incoming_administrators:
            reps_data = item["representatives"]
            reps = []

            for rep in reps_data:
                if not rep:
                    continue
                person, _ = Person.objects.get_or_create(
                    first_name=rep.get("FirstName", "").strip(),
                    last_name=rep.get("LastName", "").strip()
                )
                reps.append(person)

            admin, _ = Administrator.objects.get_or_create(
                administering_company=item["administering_company"],
                annual_account=account_lookup[ref],
                mandate=item["mandate"]
            )

            admin.representatives.set(reps)         