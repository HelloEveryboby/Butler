class ChecklistModule:
    def generate_business_checklist(self, scenario):
        checklists = {
            "payment": [
                "Verify if the price can be modified in the request (Parameter Tampering)",
                "Test for race conditions during balance deduction",
                "Check if the payment status can be forced to 'success' via callback manipulation",
                "Validate if negative amounts are accepted"
            ],
            "login": [
                "Test for brute force resistance",
                "Check for account enumeration via error messages",
                "Verify session invalidation after logout",
                "Test for 'Remember Me' token security"
            ]
        }

        relevant = []
        for key in checklists:
            if key in scenario.lower():
                relevant.extend(checklists[key])

        if not relevant:
            relevant = ["Perform standard OWASP Top 10 validation", "Check for authorization bypass"]

        return relevant
