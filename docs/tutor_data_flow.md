# Topology AI Tutor: Prototype Data Flow

**Status:** Working beta prototype; production hosting and institutional requirements remain to be determined.  
**Potential course use:** Undergraduate Topology, Spring 2027.

## Purpose

The application provides a course-specific AI tutor that functions somewhat like additional office hours. It discusses course concepts, asks questions, and critiques students' reasoning and drafts, but is instructed not to write homework solutions for them. Use in the course would be strongly encouraged but not required.

## Current data flow

| Stage | Data involved | Destination and current handling |
|---|---|---|
| 1. Student enters beta | Random individual tester code | The application stores a pseudonymous student identifier derived from the code. It does not request or store a name, email address, EMPLID, or Canvas identity. Any separately maintained code-to-student association would exist outside the application. |
| 2. Student selects work | Mode, assignment/problem or assigned conversation, and conversation title | Stored in the application database with a randomly generated conversation ID, timestamps, and tutor-version identifier. |
| 3. Student sends a message | Complete text of the message | Stored in the application database with role, sequence number, and timestamp. |
| 4. Application requests an AI response | Tutor instructions; relevant course, problem, or activity context; and the prior messages needed for the conversation | Sent over the OpenAI API. The request explicitly sets `store=False`, so the application does not create an OpenAI-hosted persistent Response or conversation record. OpenAI's standard API abuse-monitoring retention may still apply; API data is not used for model training by default. |
| 5. AI response returns | Response text and token-usage totals | Response text is stored in the application database. Token counts, model name, request type, estimated cost, pseudonymous student ID, conversation ID, and timestamp are stored as a usage event. |
| 6. Student submits feedback | Helpfulness, frustration, whether too much was revealed, unnecessary-work rating, and optional comments | Stored in the application database and associated with the pseudonymous student ID and current conversation ID. |
| 7. Error occurs | Error type, provider error code when available, error message, and traceback | Written to server diagnostic logs. A failed student message is removed if no AI response was successfully produced, so it does not silently become part of later context. |

## Current storage and access

- Conversation records, messages, feedback, and usage metadata are stored in a local SQLite database on the application host.
- Course configuration, homework/activity content, and tutor instructions are stored as application files.
- Students authenticate to the beta with individual random codes. The interface retrieves conversations only for the active pseudonymous student identifier.
- Anyone with administrative access to the application host and database could technically inspect stored records. The prototype does not yet provide a dedicated instructor dashboard or role-based administrative access.
- Student transcript download/export is not yet implemented.
- No production backup, retention, deletion, or disaster-recovery policy has yet been selected.

## Information not intentionally collected

The prototype does not intentionally collect names, email addresses, EMPLIDs, grades, payment information, medical information, or demographic information. Students may nevertheless disclose identifying or sensitive information within free-text messages, so conversation content must be treated accordingly.

## Production decisions requiring FSU guidance

| Decision | Current status |
|---|---|
| FSU-approved hosting environment | To be determined |
| Authentication method, ideally FSU or Canvas-based | To be determined |
| Production database and encryption requirements | To be determined |
| Whether OpenAI API processing requires vendor/security review or additional contractual controls | To be determined |
| FERPA status of identifiable or linkable conversations | To be determined |
| Instructor access rules and audit logging | To be determined |
| Student transcript access/export procedure | To be implemented |
| Retention and deletion schedule, including backups and diagnostic logs | To be determined |
| Incident-reporting procedure | To be determined |
| Separation of instructional use from any future research use | To be determined before research use |

OpenAI's current API data-control documentation is available at <https://developers.openai.com/api/docs/guides/your-data>.
