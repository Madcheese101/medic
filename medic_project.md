Project: Medic
Desc: POS page for a hospital built on frappe and erpnext.
`<ref_app>: /apps/social_ads.`
`<app>: medic`

## **Packages:**

 - Vuetify@3.7.19 --legacy-peer-deps
 - Vue (Already provided by frappe.)
 - Pinia (Already provided by frappe.)

## **Styling and Layout**

- For the theme and layout please check the sister app in the same
   parent folder: `<ref_app>`.
- Make sure it is mobile friendly.

## Caveats & Fix

- Make sure to check how we handle the native frappe dialogs above our dialogs (`<ref_app>`)
- Make sure it responds to the language set in frappe.
- Make sure it is RTL compatible - Depends on point above.
- The Theme is one theme as in `<ref_app>`
- Use `frappe.qb.get_query` for complex queries
- ***USE MY CUSTOM CLAUDE INSTRUCTIONS FILE.***

## Pinia Stores:

One Store to hold these values (defaults_store):
- Logged in user default POS Profile doc (loaded as entire doc)
- Logged in user roles
- Logged in user Linked Employee ID and Name if available.

## Structure/Views

For now I want a few views that I will be working on:

 1. **User Profile Image** at top bar/side bar (depends on where we place it), when clicked it gives a few options, Profile, Schedule, Logout
	- when Profile is clicked it opens a user profile view to edit user password, language, and Profile picture, that all edits the User's document from User Doctype.
	- When Schedule is clicked, it opens Availability Schedule View which should represent the Doctor Schedule doctype (you can find the doctype in the <app> folder).
	- logout simply executes frappe's logout.

 2. **Patients View**: this is the list of customers (Erpnext' Customer doctype), it should have:
	1. A button to add new Patient (Customer Name, Date of Birth, Mobile No, Blood Type,  and Gender. -ALL ARE MANDATORY except for blood type-)
	2. Filtering section: Customer Name, Mobile Number, File No -document name-; these filters are applied directly on the DB
	3. Table/List to show filtered Patients, with an Eye button at the end to show the selected customer info.
	4. Patient View (*Customer Doctype)*: it should have these info,
		* Customer Name, Date of Birth, Mobile No, Blood Type,  and Gender
		* Customer's Current Balance, should be as a colored chip, and the color depends if the customer has balance or we want money from him.
		* A section to show Patient's Medical History (Medical History doctype in `<app>`).
		* There should be a save button for the normal Customer Doctype, and another Save button for the Medical History section.


as for the rest, we'll figure it out as we go. but this is the base line for me now.
