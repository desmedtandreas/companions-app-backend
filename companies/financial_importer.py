from django.db import transaction
import requests

from datetime import datetime
from .nbb_api import get_references, get_accounting_data
from .models import Company, AnnualAccount, FinancialRubric, Administrator, Person, Participation

@transaction.atomic
def import_financials(enterprise_number):
    AnnualAccount.objects.filter(company__number=enterprise_number).delete()
    company = Company.objects.get(number=enterprise_number)
    references = get_references(enterprise_number)

    incoming_refs = [
        {
            "reference": r.get('ReferenceNumber'),
            "end_date": r.get('ExerciseDates', {}).get('endDate')
        }
        for r in references if r.get('ReferenceNumber')
    ]

    incoming_ref_numbers = [ref["reference"] for ref in incoming_refs]

    existing_refs = set(
        AnnualAccount.objects.filter(reference__in=incoming_ref_numbers)
        .values_list('reference', flat=True)
    )

    new_accounts_data = [
        ref for ref in incoming_refs if ref["reference"] not in existing_refs
    ]

    AnnualAccount.objects.bulk_create([
        AnnualAccount(
            company=company,
            reference=ref["reference"],
            end_fiscal_year=ref["end_date"]
        ) for ref in new_accounts_data
    ], batch_size=500)

    new_references = [ref["reference"] for ref in new_accounts_data]

    account_lookup = {
        acc.reference: acc for acc in AnnualAccount.objects.filter(reference__in=new_references)
    }

    # Cache companies for admin/participations
    referenced_company_ids = set()
    for ref in new_references:
        try:
            data = get_accounting_data(ref)
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                continue
            else:
                continue
        except Exception as e:
            continue
        for legal in data.get('Administrators', {}).get('LegalPersons', []):
            if id := legal.get('Entity', {}).get('Identifier'):
                referenced_company_ids.add(id)
        for part in data.get('ParticipatingInterests', []):
            if id := part.get('Entity', {}).get('Identifier'):
                referenced_company_ids.add(id)

    company_cache = {
        c.number: c for c in Company.objects.filter(number__in=referenced_company_ids)
    }

    # Cache for persons to avoid redundant queries
    person_cache = {}

    for ref in new_references:
        try:
            accounting_data = get_accounting_data(ref)
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                continue
            else:
                continue
        except Exception as e:
            continue

        annual_account = account_lookup[ref]

        # FinancialRubrics
        FinancialRubric.objects.bulk_create([
            FinancialRubric(
                code=r.get('Code'),
                value=r.get('Value'),
                annual_account=annual_account
            )
            for r in accounting_data.get('Rubrics', [])
            if r.get('Period') == 'N'
        ], batch_size=200)

        # Administrators
        incoming_admins = []

        for legalEntity in accounting_data.get('Administrators', {}).get('LegalPersons', []):
            reps = legalEntity.get('Representatives')
            company_number = legalEntity.get('Entity', {}).get('Identifier')
            if company_number not in company_cache:
                continue

            incoming_admins.append({
                "administering_company": company_cache[company_number],
                "representatives": reps
            })

        for naturalPerson in accounting_data.get('Administrators', {}).get('NaturalPersons', []):
            reps = [naturalPerson.get('Person', {})]
            incoming_admins.append({
                "administering_company": None,
                "representatives": reps
            })

        for item in incoming_admins:
            reps_data = item["representatives"] or []
            rep_objs = []

            for rep in reps_data:
                key = (rep.get("FirstName", "").strip(), rep.get("LastName", "").strip())
                if not key[0] and not key[1]:
                    continue
                if key not in person_cache:
                    person_cache[key], _ = Person.objects.get_or_create(
                        first_name=key[0], last_name=key[1]
                    )
                rep_objs.append(person_cache[key])

            admin = Administrator.objects.create(
                administering_company=item["administering_company"],
                annual_account=annual_account
            )
            if rep_objs:
                admin.representatives.set(rep_objs)

        # Participations
        participations = []
        for part in accounting_data.get('ParticipatingInterests', []):
            company_number = part.get('Entity', {}).get('Identifier')
            held_company = company_cache.get(company_number)
            if not held_company:
                continue

            for interest in part.get('ParticipatingInterestHeld', []):
                if interest.get('Nature') == 'Aandelen':
                    pct = interest.get('PercentageDirectlyHeld')
                    stocks = interest.get('Number')
                    if pct and stocks:
                        participations.append(Participation(
                            held_company=held_company,
                            percentage=pct,
                            stocks=stocks,
                            annual_account=annual_account
                        ))

        Participation.objects.bulk_create(participations, batch_size=200)

    company.fin_fetch = datetime.now()
    company.save()