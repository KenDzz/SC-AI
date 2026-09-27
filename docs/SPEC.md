You are a senior full-stack engineer, computer vision engineer, and solution architect.

Build a complete working POC application named:

"AI Safety & Compliance Monitoring POC"

The application is for a coffee manufacturing factory.

IMPORTANT:
I am not a highly technical user.
Do not only explain architecture.
Actually create the complete working project, source code, Docker configuration, database migrations, seed data, sample configuration, README, and commands required to run it.

The entire application MUST run locally using:

docker compose up -d --build

Do not require Kubernetes for this POC.

==================================================
1. BUSINESS GOAL
==================================================

The purpose of this POC is to prove that existing factory CCTV/IP camera streams can be analyzed by AI to automatically detect safety, hygiene, and restricted-area violations.

The system should behave like a "virtual safety monitoring assistant".

The system watches camera streams continuously.

When a violation happens:

Camera
→ AI detects person/object
→ system checks factory rules
→ creates incident
→ saves snapshot / short evidence clip
→ displays alert on dashboard
→ human operator reviews the incident

The AI does NOT make disciplinary decisions.

A human user must be able to mark an event as:

Confirmed
False Positive
Resolved

The False Positive feedback must be stored for future model improvement.

==================================================
2. POC SCOPE
==================================================

Implement these 5 primary business use cases.

USE CASE 1 — Restricted Area Intrusion

Admin can draw a polygon on a camera image.

Example:

Restricted Zone A

When a tracked person enters this polygon and remains there longer than a configurable duration:

Create incident:

RESTRICTED_AREA_INTRUSION

The zone and duration must be configurable.

Do NOT train an AI model for restricted zones.

Use:

Person Detection
+
Person Tracking
+
Polygon / Zone Engine


USE CASE 2 — Hairnet Compliance

For selected factory zones such as Packing Area:

Detect if a person is:

HAIRNET
NO_HAIRNET
UNKNOWN

IMPORTANT:

UNKNOWN must NOT automatically generate a violation.

Only:

NO_HAIRNET

should generate an incident when the configured rule requires hairnet.


USE CASE 3 — Uniform Compliance

For selected production zones determine:

CORRECT_UNIFORM
INCORRECT_UNIFORM
UNKNOWN

Make this AI capability modular.

The POC may initially use a configurable/custom model adapter.

Do not tightly couple the whole system to one specific model library.


USE CASE 4 — Machine Danger Zone Intrusion

Allow an administrator to define a machine danger zone using a polygon.

Example:

Machine A
Danger Zone

If a person enters the danger zone:

Create:

MACHINE_DANGER_ZONE_INTRUSION

The POC does not need PLC integration yet.

However design the rule schema so that in the future it can support:

machine_running = true / false


USE CASE 5 — Forklift / Pedestrian Zone Monitoring

Support:

Forklift detection
Person detection
Person tracking

Allow admin to create:

Forklift Lane
Pedestrian Restricted Zone

For the initial POC:

Detect a person entering a forklift lane.

Create:

PEDESTRIAN_IN_FORKLIFT_ZONE

Design the architecture so that a future version can add:

person-to-forklift distance
trajectory prediction
collision risk

Do NOT implement advanced collision prediction in the first version.

==================================================
3. OPTIONAL USE CASE
==================================================

Design the architecture so that later we can add:

Smoking / Vaping detection

but it is NOT mandatory for the first working version.

==================================================
4. INPUT SOURCES
==================================================

The AI worker must support two sources:

1. RTSP camera stream

Example:

rtsp://username:password@camera-ip/stream


2. Local uploaded MP4 video

This is very important.

Because during POC development I may not have access to the real factory camera.

I must be able to upload a sample MP4 video and use it exactly like a camera source.

Each camera should have:

id
name
factory
area
stream_type

RTSP
FILE

stream_url

enabled / disabled

AI processing FPS

Example:

CAM-PACKING-01
Packing Area Camera 01
RTSP
5 FPS AI inference

==================================================
5. TECH STACK
==================================================

Use this architecture.

Frontend:

Next.js
React
TypeScript
Tailwind CSS

Backend API:

Python
FastAPI
SQLAlchemy
Pydantic

AI Worker:

Python
OpenCV
GStreamer support
PyTorch / ONNX Runtime

Create a model abstraction layer.

Example:

Detector interface

detect(frame)

Tracker interface

update(detections)

PPEClassifier interface

classify(person_crop)


Tracking:

Use ByteTrack or another permissively licensed open-source tracking implementation.

Do not build tracking from scratch.


Database:

PostgreSQL


Cache / lightweight event communication:

Redis


Object storage:

MinIO

Use MinIO to store:

incident screenshots
short incident video clips


Do NOT store images or videos directly inside PostgreSQL.


Reverse proxy:

Nginx optional.

For local Docker development it is okay for services to expose individual ports.


Deployment:

Docker
Docker Compose


Monitoring:

Expose application health endpoints.

Prepare Prometheus-compatible metrics if practical.

Do NOT deploy a large monitoring stack unless needed.


==================================================
6. IMPORTANT MODEL DESIGN
==================================================

Do NOT tightly couple the product to one AI model.

Create adapters.

Example:

app/ai/models/

person_detector.py
ppe_classifier.py
forklift_detector.py


Common interfaces should look conceptually like:

Detector.detect(frame)

returns:

[
 {
   class_name,
   confidence,
   bbox
 }
]


Tracker.update()

returns:

track_id
bbox
class
confidence


PPE classifier returns:

{
   hairnet: "YES" | "NO" | "UNKNOWN",
   uniform: "CORRECT" | "INCORRECT" | "UNKNOWN",
   confidence: ...
}


The system must still run even if custom Hairnet / Uniform model weights are not available.

Create two modes:

REAL_AI_MODE

DEMO_MODE


DEMO_MODE should make it possible to demonstrate the complete platform without proprietary model weights.

Do NOT fake business logic silently.

The UI must clearly show:

AI Mode: DEMO

when demo inference is being used.


For Person and Forklift detection use an available permissively licensed pre-trained object detection model if possible.

Avoid creating unnecessary licensing problems.

Document the selected model and license in README.

==================================================
7. VIDEO PROCESSING ARCHITECTURE
==================================================

Do NOT send every video frame through the backend REST API.

Architecture must be:

Camera / MP4
    ↓
AI Worker
    ↓
Detection
    ↓
Tracking
    ↓
Zone Engine
    ↓
Rule Engine
    ↓
Incident Event
    ↓
Backend / Database


The backend should mainly receive:

metadata
incident information
snapshot path
video clip path

not raw continuous video frames.

Each AI worker should be independently scalable.

Design it so later we can run:

AI Worker 01
CAM01-CAM05

AI Worker 02
CAM06-CAM10

AI Worker 03
CAM11-CAM15


Do NOT hard-code camera assignment.

==================================================
8. ZONE ENGINE
==================================================

Implement a reusable Zone Engine.

Admin must be able to draw polygon zones on top of a camera snapshot.

Zone types:

RESTRICTED_AREA
MACHINE_DANGER_ZONE
FORKLIFT_LANE
PRODUCTION_ZONE
PACKING_ZONE


Example stored polygon:

[
  [0.12, 0.20],
  [0.78, 0.20],
  [0.82, 0.82],
  [0.10, 0.80]
]

Prefer normalized coordinates from 0 to 1.

This allows the zone to survive video resolution changes.


Implement:

point in polygon
bbox center in polygon

and structure the code so future versions can support:

bbox overlap %
line crossing
trajectory
distance


Use an appropriate geometry library such as Shapely if useful.

==================================================
9. RULE ENGINE
==================================================

This is very important.

Do NOT hard-code rules like:

if no_hairnet:
    alert()

Rules must come from database configuration.


Example:

Rule:

PACKING_HAIRNET

Zone:
PACKING_ZONE_01

Condition:

hairnet == NO

Minimum duration:

2 seconds

Cooldown:

30 seconds

Severity:

HIGH


Another rule:

MACHINE_ZONE_INTRUSION

Zone:
MACHINE_01_DANGER

Condition:

person_inside_zone == true

Minimum duration:

1 second

Severity:

CRITICAL


Another:

FORKLIFT_LANE_INTRUSION

Condition:

person_inside_zone == true


Design a generic rule structure that can later support:

machine_running
employee_role
access_authorized
time_schedule
sensor_value


but do not overbuild these integrations now.

==================================================
10. INCIDENT DEDUPLICATION
==================================================

Do not generate an incident every video frame.

Example:

Person #123 has no hairnet for 5 seconds.

This must create:

1 incident

NOT:

150 incidents.


Use:

track_id
rule_id
camera_id
cooldown
violation duration


to deduplicate incidents.

==================================================
11. INCIDENT EVIDENCE
==================================================

When an incident is created:

Save:

snapshot image

and when technically practical:

short video clip


Suggested clip:

5 seconds before event
+
5 seconds after event


If pre-event video buffering is too complex for the first implementation:

Implement snapshot first.

Structure the code so video evidence can be added without rewriting the system.

Store files in MinIO.

Database should store:

object key / URI

not binary media.

==================================================
12. DATABASE ENTITIES
==================================================

Create proper relational database models.

At minimum:

Factory

Camera

Zone

Rule

Incident

IncidentEvidence

AIModel

AIModelDeployment

OperatorFeedback


Incident should contain:

id
factory_id
camera_id
zone_id
rule_id

event_type

severity

track_id

confidence

started_at
ended_at

status

NEW
CONFIRMED
FALSE_POSITIVE
RESOLVED

snapshot_uri

clip_uri

model_name
model_version

created_at
updated_at


OperatorFeedback:

incident_id

decision

comment

user

created_at


Create migrations.

Use Alembic.

==================================================
13. DASHBOARD
==================================================

Create a modern, clean, professional factory monitoring dashboard.

Design language:

industrial
modern
clean
not overly futuristic
easy to understand for factory managers


Pages:

1. Overview Dashboard

Show:

Active Cameras
Incidents Today
Critical Incidents
Confirmed Incidents
False Positive Rate


Show incident trend chart.


Show latest incidents.


2. Camera Management

Display camera cards.

Camera status:

Online
Offline
AI Processing
Disabled


Allow:

add camera
edit camera
enable / disable camera
configure AI FPS


Support:

RTSP
MP4 upload


3. Camera Detail

Show camera preview.

Overlay:

person bounding boxes
track IDs
zones

Example:

Person #21

Hairnet: NO

Uniform: CORRECT


Provide switch:

Show AI overlay ON/OFF


4. Zone Configuration

Take current frame from camera.

Allow user to draw polygon with mouse.

Set:

Zone name
Zone type


Save normalized coordinates.


5. Rule Management

User can create/edit rules.

Examples:

Hairnet Required
Restricted Area
Machine Danger Zone
Forklift Lane


6. Incident Management

Table columns:

Timestamp
Camera
Zone
Violation
Severity
Confidence
Status
Evidence


Filters:

date
camera
zone
violation type
severity
status


7. Incident Detail

Show:

snapshot
video if available

camera
zone
rule
AI confidence
model version
event timestamps


Actions:

Confirm
False Positive
Resolve

Add comment.


8. AI Models

Simple page.

Show:

Model
Version
Type
Status
Created Date

Example:

person-detector
v1.0
ACTIVE


ppe-classifier
v0.1
DEMO


Do NOT build complicated MLflow UI integration inside the application.

==================================================
14. USER EXPERIENCE
==================================================

The UI must be understandable by a non-technical factory manager.

Avoid showing technical AI terminology everywhere.

For example instead of:

"Bounding box inference confidence"

use:

"AI Confidence"


Instead of:

"Class = person"

use:

"Person detected"


Use clear severity:

LOW
MEDIUM
HIGH
CRITICAL


Use visual labels and status badges.

==================================================
15. DEMO DATA
==================================================

Create seed data.

Factory:

Coffee Factory POC


Areas:

Packing Area
Production Area
Machine Area
Warehouse


Cameras:

CAM-PACK-01
CAM-PROD-01
CAM-MACHINE-01
CAM-WAREHOUSE-01


Create sample zones.

Create sample rules.

Create sample incidents.

The dashboard should look populated immediately after startup.

==================================================
16. DOCKER REQUIREMENTS
==================================================

Create:

docker-compose.yml

Services should include:

frontend

backend

ai-worker

postgres

redis

minio


Optional:

nginx


Everything must start using:

docker compose up -d --build


Create:

.env.example


Important environment variables:

DATABASE_URL

REDIS_URL

MINIO_ENDPOINT

MINIO_ACCESS_KEY

MINIO_SECRET_KEY

AI_MODE

MODEL_PATH

DEFAULT_AI_FPS


Use Docker healthchecks.

Services must wait correctly for required dependencies.

Do not use localhost incorrectly inside Docker networking.

Use Docker service names.

Example:

postgres:5432

redis:6379

minio:9000


Add persistent Docker volumes for:

PostgreSQL

MinIO


==================================================
17. GPU SUPPORT
==================================================

The project must work in CPU mode for development.

Also document optional NVIDIA GPU support.

Create a profile or documented configuration for:

NVIDIA Container Toolkit


Example desired future execution:

docker compose --profile gpu up -d


But CPU mode must remain available.


Do not make GPU mandatory just to open the dashboard.

==================================================
18. PROJECT STRUCTURE
==================================================

Keep the repository clean.

Suggested architecture:

/apps
  /frontend
  /backend
  /ai-worker

/packages
  /shared-schemas

/infrastructure
  /docker

/sample-data
  /videos

/docs


Avoid unnecessary microservices.

The POC should remain understandable by a small engineering team.

==================================================
19. API
==================================================

Create REST APIs.

Suggested resources:

/api/factories

/api/cameras

/api/cameras/{id}/snapshot

/api/zones

/api/rules

/api/incidents

/api/incidents/{id}

/api/incidents/{id}/confirm

/api/incidents/{id}/false-positive

/api/incidents/{id}/resolve

/api/models

/api/system/health


Use OpenAPI documentation automatically from FastAPI.

==================================================
20. REALTIME EVENTS
==================================================

Dashboard should receive new incidents without manual browser refresh.

Use:

WebSocket

or:

Server Sent Events


For this POC prefer the simpler reliable implementation.

==================================================
21. SECURITY
==================================================

For POC implement simple authentication.

Roles:

ADMIN

SAFETY_MANAGER

VIEWER


ADMIN:

camera configuration
zones
rules

SAFETY_MANAGER:

review incidents
confirm
false positive
resolve

VIEWER:

read only


Use JWT authentication.

Structure the project so future versions can integrate:

Keycloak
Microsoft Entra ID
corporate SSO


Do not implement corporate SSO now.

==================================================
22. LOGGING
==================================================

Use structured logs.

Every incident log should make it easy to find:

camera_id

track_id

rule_id

incident_id


Never log RTSP camera passwords.

Mask sensitive URLs.

==================================================
23. OBSERVABILITY
==================================================

Provide:

/health

/ready

/metrics


AI worker metrics should include:

camera status

frames processed

AI FPS

inference latency

detections

incidents created

dropped frames


This is important because later we need to estimate how many cameras one server can handle.

==================================================
24. PERFORMANCE PRINCIPLES
==================================================

Do not process 30 FPS just because the camera is 30 FPS.

Each camera should have configurable AI FPS.

Default:

5 FPS


Video preview can remain at normal FPS where appropriate.

AI processing should sample frames independently.


Keep AI worker stateless where practical.

Camera configuration should come from backend/database.


Later we should be able to run multiple AI workers horizontally.

==================================================
25. IMPORTANT SCALE PRINCIPLE
==================================================

POC architecture must allow this future deployment:

Factory 1

Camera 01-10
→ AI Worker 01

Camera 11-20
→ AI Worker 02


Factory 2

Camera 01-10
→ AI Worker 03


Central platform:

Backend
PostgreSQL
Object Storage
Dashboard


Do NOT implement multi-factory distributed infrastructure now.

Just make sure data models include:

factory_id

and worker architecture is not tied to one machine.

==================================================
26. OUT OF SCOPE
==================================================

Do NOT implement these in the first POC:

Face Recognition

Employee biometric identification

CO gas detection using cameras

Dust concentration measurement

Chemical / VOC detection

Fire alarm replacement

PLC integration

RFID integration

Enterprise access control integration

Complex collision prediction

Hand washing sequence recognition

Advanced behavior anomaly detection

Kubernetes

Kafka cluster

Elasticsearch

Service Mesh

Multi-region deployment


Leave extension points where appropriate.

==================================================
27. TESTING
==================================================

Add meaningful automated tests.

Backend:

unit tests
API tests

Zone Engine:

point inside polygon
outside polygon
boundary conditions

Rule Engine:

minimum duration

cooldown

duplicate suppression

UNKNOWN PPE state must not cause violation


AI Worker:

mock detector tests

tracking event tests


Frontend:

basic component / page tests if practical.


==================================================
28. POC SUCCESS METRICS
==================================================

The platform must make it possible to later measure:

Precision

Recall

False alerts per camera per hour

Missed incidents

Average inference latency

Event detection latency

AI FPS

GPU / CPU utilization


Do NOT promise 99% accuracy.

Create a simple evaluation page or export endpoint if practical.

==================================================
29. README
==================================================

Create a very clear README for a non-technical user.

Include:

What this project does

Architecture diagram using Mermaid

Requirements

How to start:

cp .env.example .env

docker compose up -d --build


How to open:

Dashboard URL

API Swagger URL

MinIO URL


Default demo username/password


How to load a sample MP4


How to create a zone


How to create a rule


How to simulate / test an incident


How CPU mode works


How optional GPU mode works


How to stop:

docker compose down


How to reset all POC data.


==================================================
30. DEVELOPMENT APPROACH
==================================================

Do not try to build everything in one giant step.

Implement in working vertical slices.

Recommended order:

Infrastructure + Docker

Database + Backend

Frontend basic dashboard

Camera/video ingestion

Person detection

Tracking

Zone engine

Restricted-area detection

Incident system

Hairnet / Uniform model adapter

Machine danger zone

Forklift zone

Realtime alerts

Operator feedback

Metrics

Testing

Documentation


After every major phase:

run tests

build Docker images

verify the application still starts


Do not leave placeholder code that prevents the application from running.


==================================================
31. IMPORTANT CODING RULES
==================================================

Prefer maintainable, readable code.

Use type hints.

Use proper error handling.

No hard-coded secrets.

No absolute local filesystem paths.

Do not store configuration only in source code.

Do not duplicate business logic between AI worker and backend.

Keep AI-specific code separate from business rule code.

Create database migrations.

Create seed scripts.

Create useful logs.

Add comments only where necessary.

Do not over-engineer.


==================================================
32. FINAL EXPECTED RESULT
==================================================

At the end I should be able to run:

git clone <repo>

cd <repo>

cp .env.example .env

docker compose up -d --build


Then open the browser.

I should see:

AI Safety & Compliance Monitoring

Dashboard

4 sample cameras

sample factory zones

sample compliance rules

sample incidents


I should also be able to:

upload an MP4

configure it as a camera source

draw a restricted zone

run AI processing

see a person enter the zone

receive an incident

view screenshot evidence

mark it as:

Confirmed
False Positive
Resolved


Most importantly:

DO NOT only generate architecture documents.

Build the actual runnable application.

When you encounter a technical decision, prefer the simplest implementation that preserves the architecture above.

Before finishing:

1. Run backend tests.
2. Run frontend build.
3. Run Docker Compose.
4. Check container health.
5. Verify migrations.
6. Verify seed data.
7. Verify dashboard loads.
8. Verify at least one end-to-end Restricted Area incident flow.
9. Fix all blocking errors.
10. Update README with the real commands that were tested.

Start implementing now.