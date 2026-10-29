# Operations Portal — User Guide

Welcome to the Operations Portal. This guide explains how to manage master-data requests, review customer records, follow approvals, and explore purchasing insights.

**[Open the Operations Portal](https://dsa-competition-4w84ptpcxfowwbvj5l3kkh.streamlit.app/)**

## Get started

Use the navigation menu on the left to move between workspaces. The **Viewing as** control identifies the role currently being displayed. In this demonstration environment, it lets you see how the workspace works for different types of employees.

| Workspace | What you can do |
| --- | --- |
| **Overview** | Check current requests, outstanding reviews, data-quality issues and key business indicators. |
| **Master Data** | Investigate suspected duplicates, create requests, track progress and review approvals. |
| **Regional Performance** | Explore purchasing trends by country, product and business unit. |
| **Insights & Forecasts** | Compare forecasting methods, produce purchasing plans and review customer opportunities. |
| **Administration** | View system settings, approval routing and operational estimates. |

Need help while working? Select **✦ Ask Operations** in the bottom-right corner for contextual guidance and shortcuts to relevant workspaces.

## Manage master data

### Find and investigate duplicate records

Open **Master Data → Quality exceptions**.

1. Use the **Market** and **Case status** filters to find records requiring attention.
2. Review each candidate's priority, proposed matching record and purchase-order exposure.
3. Choose a record under **Inspect candidate** to view its details and matching business identifier.
4. To open a new review, select **Prepare customer review**. The customer form opens with the available details prefilled.
5. Verify the information, choose the appropriate retained record if applicable, and submit the request for approval.

You can also switch to **3D identity network** to explore proposed relationships visually. Rotate or zoom the network, or point to a record for more information. This view helps investigate relationships; it does **not** automatically merge records.

**Important:** A suggested duplicate is not a confirmed match. A record is linked to another identity only after the required approvals and final master-data validation.

### Create a new customer or item request

Open **Master Data → Create request**.

1. Under **Intake channel**, select **Quick form** to enter details manually or **From email** to extract information from an existing message.
2. Select the record type, such as **Customer** or **Item**.
3. Fill in the required fields. The form checks for missing details and, where applicable, possible duplicate records. For an **Item**, choose a **Regulatory class**; any class other than *Not regulated* also requires a **product licence / registration number** before the request can reach Quality review. This rule is set in `domains.yaml` (`conditional_required`), so the MDM team can change it without code.
4. Review the suggested matches carefully. If an existing record should be retained, confirm the proposed identity-link details.
5. Select the acknowledgement checkbox and then **Submit for approval**.

The portal assigns a request reference. Use **Request tracker** to check its status.

**Creating a request from an email:** Paste the message into the email field and select **Extract and prefill**. Check every extracted value before submitting. If an optional AI extraction service is unavailable, use the rules-based extraction option.

Example request:

> Please create customer ABC Hospital under QTS in Singapore. Registration number: SG-REG-000001.

You can expand **Email routing & response simulation** to see how an incoming message would be classified and what acknowledgement would be prepared. Messages are not actually sent by this feature.

**Available record types:** Customer and Item support the complete request flow. Vendor and Cost Center are currently listed for configuration purposes.

### Track a request

Open **Master Data → Request tracker**.

Use **Filter by status** to narrow the list, or search using a request number or record name. The tracker shows requests as they move through the approval process.

| Status | Meaning |
| --- | --- |
| **Submitted** | The request has been received. |
| **In Approval** | One or more assigned reviewers are considering the request. |
| **Approved** | Required steward reviews are complete; final validation is pending. |
| **Created** | Final validation and the workspace handoff have been recorded. |
| **Rejected** | The request was not approved; no master-data change was completed. |

### Review and approve requests

Open **Master Data → Approval inbox** and select the request you need to review.

The information and actions available depend on the role currently selected in **Viewing as** in the left sidebar:

| Role | Responsibilities |
| --- | --- |
| **Requestor** | View submitted requests and monitor their progress. |
| **Finance Steward** | Review assigned customer requests. |
| **BU Steward** | Review assigned business-unit requests. |
| **Quality Steward** | Review assigned item requests. |
| **MDM Steward** | Perform final validation after the assigned stewards approve. |
| **Admin** | Maintain approval-routing configuration under Administration. |

When a review is assigned to your role, inspect the request details and supporting evidence before selecting **Approve request** or **Reject request**. For requests that have completed all steward reviews, the MDM Steward can select **Confirm and finalize**.

Customer requests normally require **Finance Steward + BU Steward** review. Item requests normally require **Quality Steward + BU Steward** review. Both then proceed to final MDM validation.

For further context, expand **Approval deadlines**, **Audit history** or **ERP handoff**, when available. The handoff provides an exportable record of the approved action; it does not mean a live company ERP has been updated.

## Explore purchasing and customer performance

Open **Regional Performance**.

- Choose a **Market**, **Product** and **Business unit** to explore confirmed purchase-order quantities.
- Review the purchasing trend and year-on-year comparisons.
- Check the featured customer evidence to understand how duplicate identities can affect account-level growth interpretation.
- Expand the source-order details to compare the original customer IDs with their consolidated view.

An approved identity link updates the way customer purchases are attributed. It **does not create additional purchase orders or change regional purchase-order totals**.

The included markets are Singapore, Malaysia, Indonesia, Thailand and Vietnam; products are grouped as A, B and C.

## Build a purchasing forecast

Open **Insights & Forecasts**.

### Review forecast accuracy

The **Compare forecast models** section shows each model's error measured using **WAPE**. Lower WAPE indicates a better result for the evaluated period.

The available PO-only forecasting methods are **six-month moving average**, **Holt–Winters**, and **pooled gradient boosting**. The additional **unfiltered-input** comparison illustrates how including non-order messages in demand data can distort analysis; it is not a method for generating purchasing plans.

### Create and export a plan

1. In **Forward purchasing plan**, choose the **Market** and **Product**.
2. Select a **6-month** or **12-month** horizon.
3. Select one of the three PO-only forecasting methods.
4. Review the monthly forecast and the low/high planning scenarios.
5. Select **Export purchasing plan (CSV)** to download the monthly quantities.

The low and high values are planning scenarios, not guaranteed demand ranges. Review them together with commercial context before making purchasing decisions.

### Review commercial opportunities

The same workspace includes **Customer drop-off watchlist** and **Cross-selling candidates**. These are indications for account managers to investigate, not automated instructions to contact customers or place orders.

The **Demand visibility** section estimates possible purchasing activity delayed by pending master-data setups. You can adjust the waiting period, proportion of requests expected to require an order and typical order value. The displayed financial amount is an **illustrative estimate**, not confirmed revenue or observed lost sales.

## Administration

Open **Administration** to view the available integration status and current **Approval routing matrix**. You can filter rules by business unit, master-data domain and country.

When using the **Admin** role in the demonstration, open **Add a new routing rule** to set an entity, domain, market, assigned steward and working-day SLA. Saved rules apply to future requests; they do not retroactively change previously assigned approvals.

The **Operational savings calculator** lets you vary request volume, processing time and hourly cost to estimate staff capacity that could be released. These figures are scenario estimates, not measured cost reductions.

## Frequently asked questions

**Why can't I approve this request?**  
The current role may not be an assigned reviewer, the request may already be complete, or the assigned review may no longer be pending. Check **Viewing as**, the selected request and its approval progress.

**Why is a potential consolidated growth figure different from the live result?**  
Proposed customer-identity changes are displayed for review, but they do not become part of the approved analytical view until all required approvals and final MDM confirmation are complete.

**What if the request has already been completed?**  
You can inspect its completed status, supporting audit history and handoff. To restore the original sample records, use **Reset demonstration** in the sidebar. A reset affects the demonstration data, so avoid using it while another person is working.

**Why do I see a forecasting model taking time to load?**  
Model comparisons can require an initial calculation. Once computed, results may load more quickly because they are cached.

**Why can't I send email notifications or create an SAP record?**  
Email replies, role changes and ERP handoffs are presented in a demonstration environment. Live enterprise connections are not part of the standard public workspace.

**Where can I get help?**  
Open **✦ Ask Operations** in the bottom-right corner of the portal.

## About this workspace

The current environment uses **sample business data** and simulated employee roles. Information you enter may be visible in a shared demonstration environment, and changes may not persist after a restart. Do not enter actual confidential or sensitive information.
