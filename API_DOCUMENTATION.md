# API Documentation - Backend GRUPO-1

## Overview

This is a complete REST API backend for a job application platform built with **FastAPI** and **PostgreSQL** (compatible with Supabase).

**Base URL (local)**: `http://localhost:8000/`

> **Nota (2026-07):** este documento describe la versión original de la API. La
> implementación actual difiere en algunos puntos; la fuente de verdad es la
> documentación interactiva en `http://localhost:8000/docs`. Cambios clave:
>
> - Todos los endpoints de negocio (vacantes, postulaciones, mensajería, métricas,
>   cuenta) requieren `Authorization: Bearer <access_token>` y validan la
>   propiedad del recurso segun el rol (`postulante`/`empresa`).
> - `POST /api/iam/registrar` solo acepta los roles `postulante` y `empresa`.
> - Endpoints agregados: `GET /api/iam/me`, `PATCH /api/iam/cuenta/{id}`,
>   `POST /api/iam/cuenta/{id}/foto` (foto de perfil, max 3 MB),
>   `POST /api/contacto/mensaje` (mensaje del hilo de una postulación) y
>   `GET /api/contacto/?postulacion_id=...`.
> - El feedback `aprobacion`/`rechazo` actualiza automaticamente el estado de la
>   postulación a `aceptado`/`rechazado` si la transición es válida.
> - `POST /api/puesto/` y `PUT /api/puesto/{id}` crean y actualizan vacantes y
>   validan el rango salarial
>   (`salario_max >= salario_min >= 0`).

---

## Table of Contents

1. [IAM (Authentication) Endpoints](#iam-authentication-endpoints)
2. [Postulación (Job Application) Endpoints](#postulación-job-application-endpoints)
3. [Vacantes (Job Openings) Endpoints](#vacantes-job-openings-endpoints)
4. [Mensajería (Contact/Feedback) Endpoints](#mensajería-contactfeedback-endpoints)
5. [Métricas (Metrics) Endpoints](#métricas-metrics-endpoints)
6. [Error Handling](#error-handling)
7. [Authentication](#authentication)

---

## IAM (Authentication) Endpoints

Base URL: `/api/iam`

### 1. Register User

**Endpoint**: `POST /iam/registrar`

**Purpose**: Create a new user account

**Request Body**:
```json
{
  "nombre_completo": "Juan Pérez",
  "email": "juan@example.com",
  "password": "SecurePass123!",
  "carrera": "Ingeniería en Sistemas",
  "telefono": "+34612345678",
  "ciudad": "Madrid",
  "rol": "postulante"
}
```

**Parameters**:
- `nombre_completo` (string, required): Full name of the user
- `email` (string, required): Unique email address
- `password` (string, required): Password (minimum 8 characters, must contain uppercase, lowercase, number, and special character)
- `carrera` (string, optional): Career/field of study
- `telefono` (string, optional): Phone number
- `ciudad` (string, optional): City of residence
- `rol` (string, optional): User role - default: "postulante"

**Response** (201 Created):
```json
{
  "cuenta_id": "550e8400-e29b-41d4-a716-446655440000",
  "nombre_completo": "Juan Pérez",
  "email": "juan@example.com",
  "carrera": "Ingeniería en Sistemas",
  "telefono": "+34612345678",
  "ciudad": "Madrid",
  "rol": "postulante",
  "estado": "pendiente_verificacion",
  "fecha_creacion": "2025-11-30T10:30:00",
  "fecha_actualizacion": null,
  "fecha_primer_acceso": null
}
```

**Error Responses**:
- `400 Bad Request`: Invalid data or email already exists
- `400 Bad Request`: Password doesn't meet requirements

---

### 2. Login

**Endpoint**: `POST /iam/login`

**Purpose**: Authenticate user and get JWT tokens

**Request Body**:
```json
{
  "email": "juan@example.com",
  "password": "SecurePass123!"
}
```

**Parameters**:
- `email` (string, required): User email
- `password` (string, required): User password

**Response** (200 OK):
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "cuenta_id": "550e8400-e29b-41d4-a716-446655440000",
  "email": "juan@example.com",
  "rol": "postulante"
}
```

**Error Responses**:
- `401 Unauthorized`: Invalid email or password
- `400 Bad Request`: Login error

---

### 3. Refresh Token

**Endpoint**: `POST /iam/refresh-token`

**Purpose**: Get a new access token using refresh token

**Request Body**:
```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Parameters**:
- `refresh_token` (string, required): Valid refresh token from login

**Response** (200 OK):
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "cuenta_id": "550e8400-e29b-41d4-a716-446655440000",
  "email": "juan@example.com",
  "rol": "postulante"
}
```

**Error Responses**:
- `401 Unauthorized`: Invalid or expired refresh token
- `401 Unauthorized`: Wrong token type
- `404 Not Found`: Account not found

---

### 4. Change Password

**Endpoint**: `POST /iam/cambiar-password`

**Purpose**: Change user password

**Request Body**:
```json
{
  "password_actual": "OldPass123!",
  "password_nuevo": "NewPass456!"
}
```

**Parameters**:
- `password_actual` (string, required): Current password
- `password_nuevo` (string, required): New password
- `cuenta_id` (string, required, from header/parameter): Account ID

**Response** (200 OK):
```json
{
  "mensaje": "Contraseña actualizada exitosamente",
  "exito": true
}
```

**Error Responses**:
- `400 Bad Request`: Invalid current password
- `400 Bad Request`: Password change error

---

### 5. Get Account Info

**Endpoint**: `GET /iam/cuenta/{cuenta_id}`

**Purpose**: Retrieve user account information

**Path Parameters**:
- `cuenta_id` (string, required): User account ID

**Response** (200 OK):
```json
{
  "cuenta_id": "550e8400-e29b-41d4-a716-446655440000",
  "nombre_completo": "Juan Pérez",
  "email": "juan@example.com",
  "carrera": "Ingeniería en Sistemas",
  "telefono": "+34612345678",
  "ciudad": "Madrid",
  "rol": "postulante",
  "estado": "activo",
  "fecha_creacion": "2025-11-30T10:30:00",
  "fecha_actualizacion": "2025-11-30T15:45:00",
  "fecha_primer_acceso": "2025-11-30T11:00:00"
}
```

**Error Responses**:
- `404 Not Found`: Account not found
- `400 Bad Request`: Error retrieving account

---

### 6. Get Account by Email

**Endpoint**: `GET /iam/cuenta/email/{email}`

**Purpose**: Retrieve user account information by email

**Path Parameters**:
- `email` (string, required): User email address

**Response** (200 OK):
```json
{
  "cuenta_id": "550e8400-e29b-41d4-a716-446655440000",
  "nombre_completo": "Juan Pérez",
  "email": "juan@example.com",
  "carrera": "Ingeniería en Sistemas",
  "telefono": "+34612345678",
  "ciudad": "Madrid",
  "rol": "postulante",
  "estado": "activo",
  "fecha_creacion": "2025-11-30T10:30:00",
  "fecha_actualizacion": "2025-11-30T15:45:00",
  "fecha_primer_acceso": "2025-11-30T11:00:00"
}
```

**Error Responses**:
- `404 Not Found`: Account not found with that email
- `400 Bad Request`: Error retrieving account

---

### 7. Verify Token

**Endpoint**: `POST /iam/verificar-token`

**Purpose**: Check if a JWT token is valid

**Request Body**:
```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Parameters**:
- `refresh_token` (string, required): Token to verify (can be access or refresh token)

**Response** (200 OK):
```json
{
  "valido": true,
  "cuenta_id": "550e8400-e29b-41d4-a716-446655440000",
  "rol": "postulante"
}
```

**Or if invalid**:
```json
{
  "valido": false,
  "cuenta_id": null,
  "rol": null
}
```

**Error Responses**:
- `400 Bad Request`: Token verification error

---

## Postulación (Job Application) Endpoints

Base URL: `/api/postulacion`

### Data Enrichment Feature

All postulacion endpoints automatically enrich responses with related data:

**Enriched Data Includes**:
- **Postulante**: Full applicant information (name, email, career, phone, city)
- **Vacante**: Complete vacancy details (title, description, location, salary, contract type)
- **Empresa**: Company information (name, email)

**Why?** 
The frontend no longer needs to make separate API calls to fetch applicant, vacancy, and company information. All related data is returned in a single response, reducing API calls and improving performance.

**Disabling Enrichment**:
If you only need basic data, add `?enriquecer=false` to the list endpoint:
```
GET /postulacion/?candidato_id=550e8400-e29b-41d4-a716-446655440000&enriquecer=false
```

### 1. Create Application

**Endpoint**: `POST /postulacion/`

**Purpose**: Submit a job application for a specific position

**Request Body**:
```json
{
  "candidato_id": "550e8400-e29b-41d4-a716-446655440000",
  "puesto_id": "660e8400-e29b-41d4-a716-446655440001",
  "documentos_adjuntos": [
    {
      "nombre": "CV.pdf",
      "url": "https://storage.example.com/cv.pdf",
      "tipo": "pdf"
    }
  ]
}
```

**Parameters**:
- `candidato_id` (string, required): ID of the job applicant
- `puesto_id` (string, required): ID of the vacancy
- `documentos_adjuntos` (array, optional): Array of attached documents with name, url, and type

**Response** (201 Created):
```json
{
  "postulacion_id": "770e8400-e29b-41d4-a716-446655440002",
  "fecha_postulacion": "2025-11-30T10:30:00",
  "estado": "pendiente",
  "documentos_adjuntos": [
    {
      "nombre": "CV.pdf",
      "url": "https://storage.example.com/cv.pdf",
      "tipo": "pdf"
    }
  ],
  "hitos": [],
  "candidato": {
    "cuenta_id": "550e8400-e29b-41d4-a716-446655440000",
    "nombre_completo": "Juan Pérez",
    "email": "juan@example.com",
    "carrera": "Ingeniería en Sistemas",
    "telefono": "+34612345678",
    "ciudad": "Madrid"
  },
  "puesto": {
    "puesto_id": "660e8400-e29b-41d4-a716-446655440001",
    "titulo": "Desarrollador Full Stack Senior",
    "descripcion": "Buscamos un desarrollador con experiencia en React y Node.js",
    "ubicacion": "Ciudad de México",
    "salario_min": 25000,
    "salario_max": 35000,
    "moneda": "PEN",
    "tipo_contrato": "tiempo_completo",
    "empresa_id": "550e8400-e29b-41d4-a716-446655440000"
  },
  "empresa": {
    "empresa_id": "550e8400-e29b-41d4-a716-446655440000",
    "nombre": "TechCorp Inc",
    "email": "careers@techcorp.com"
  }
}
```

**Error Responses**:
- `400 Bad Request`: Invalid data or vacancy not found

---

### 2. Get Application

**Endpoint**: `GET /postulacion/{postulacion_id}`

**Purpose**: Retrieve details of a specific job application with enriched data

**Path Parameters**:
- `postulacion_id` (string, required): ID of the application

**Response** (200 OK):
```json
{
  "postulacion_id": "770e8400-e29b-41d4-a716-446655440002",
  "fecha_postulacion": "2025-11-30T10:30:00",
  "estado": "en_revision",
  "documentos_adjuntos": [
    {
      "nombre": "CV.pdf",
      "url": "https://storage.example.com/cv.pdf",
      "tipo": "pdf"
    }
  ],
  "hitos": [
    {
      "hito_id": "880e8400-e29b-41d4-a716-446655440003",
      "fecha": "2025-11-30T14:00:00",
      "descripcion": "CV revisado"
    }
  ],
  "candidato": {
    "cuenta_id": "550e8400-e29b-41d4-a716-446655440000",
    "nombre_completo": "Juan Pérez",
    "email": "juan@example.com",
    "carrera": "Ingeniería en Sistemas",
    "telefono": "+34612345678",
    "ciudad": "Madrid"
  },
  "puesto": {
    "puesto_id": "660e8400-e29b-41d4-a716-446655440001",
    "titulo": "Desarrollador Full Stack Senior",
    "descripcion": "Buscamos un desarrollador con experiencia en React y Node.js",
    "ubicacion": "Ciudad de México",
    "salario_min": 25000,
    "salario_max": 35000,
    "moneda": "PEN",
    "tipo_contrato": "tiempo_completo",
    "empresa_id": "550e8400-e29b-41d4-a716-446655440000"
  },
  "empresa": {
    "empresa_id": "550e8400-e29b-41d4-a716-446655440000",
    "nombre": "TechCorp Inc",
    "email": "careers@techcorp.com"
  }
}
```

**Error Responses**:
- `404 Not Found`: Application not found

---

### 3. List Applications

**Endpoint**: `GET /postulacion/`

**Purpose**: List all applications with optional filters and automatic data enrichment

**Query Parameters**:
- `candidato_id` (string, optional): Filter by applicant ID
- `puesto_id` (string, optional): Filter by vacancy ID
- `estado` (string, optional): Filter by application status (pendiente, en_revision, entrevista, aceptado, rechazado)
- `enriquecer` (boolean, optional): Include enriched data (default: true) - set to false to get only basic info

**Response** (200 OK) - With enrichment (default):
```json
[
  {
    "postulacion_id": "770e8400-e29b-41d4-a716-446655440002",
    "fecha_postulacion": "2025-11-30T10:30:00",
    "estado": "en_revision",
    "documentos_adjuntos": [],
    "hitos": [],
    "candidato": {
      "cuenta_id": "550e8400-e29b-41d4-a716-446655440000",
      "nombre_completo": "Juan Pérez",
      "email": "juan@example.com",
      "carrera": "Ingeniería en Sistemas",
      "telefono": "+34612345678",
      "ciudad": "Madrid"
    },
    "puesto": {
      "puesto_id": "660e8400-e29b-41d4-a716-446655440001",
      "titulo": "Desarrollador Full Stack Senior",
      "descripcion": "Buscamos un desarrollador con experiencia en React y Node.js",
      "ubicacion": "Ciudad de México",
      "salario_min": 25000,
      "salario_max": 35000,
      "moneda": "PEN",
      "tipo_contrato": "tiempo_completo",
      "empresa_id": "550e8400-e29b-41d4-a716-446655440000"
    },
    "empresa": {
      "empresa_id": "550e8400-e29b-41d4-a716-446655440000",
      "nombre": "TechCorp Inc",
      "email": "careers@techcorp.com"
    }
  }
]
```

**Response** (200 OK) - Without enrichment (`?enriquecer=false`):
```json
[
  {
    "postulacion_id": "770e8400-e29b-41d4-a716-446655440002",
    "candidato_id": "550e8400-e29b-41d4-a716-446655440000",
    "puesto_id": "660e8400-e29b-41d4-a716-446655440001",
    "fecha_postulacion": "2025-11-30T10:30:00",
    "estado": "en_revision",
    "documentos_adjuntos": [],
    "hitos": []
  }
]
```

**Error Responses**:
- `400 Bad Request`: Invalid filter parameters

---

### 4. Update Application Status

**Endpoint**: `PATCH /postulacion/{postulacion_id}/estado`

**Purpose**: Update the status of a job application and receive enriched data

**Path Parameters**:
- `postulacion_id` (string, required): ID of the application

**Request Body**:
```json
{
  "nuevo_estado": "entrevista"
}
```

**Parameters**:
- `nuevo_estado` (string, required): New status - Valid values: pendiente, en_revision, entrevista, aceptado, rechazado

**Response** (200 OK):
```json
{
  "postulacion_id": "770e8400-e29b-41d4-a716-446655440002",
  "fecha_postulacion": "2025-11-30T10:30:00",
  "estado": "entrevista",
  "documentos_adjuntos": [],
  "hitos": [],
  "candidato": {
    "cuenta_id": "550e8400-e29b-41d4-a716-446655440000",
    "nombre_completo": "Juan Pérez",
    "email": "juan@example.com",
    "carrera": "Ingeniería en Sistemas",
    "telefono": "+34612345678",
    "ciudad": "Madrid"
  },
  "puesto": {
    "puesto_id": "660e8400-e29b-41d4-a716-446655440001",
    "titulo": "Desarrollador Full Stack Senior",
    "descripcion": "Buscamos un desarrollador con experiencia en React y Node.js",
    "ubicacion": "Ciudad de México",
    "salario_min": 25000,
    "salario_max": 35000,
    "moneda": "PEN",
    "tipo_contrato": "tiempo_completo",
    "empresa_id": "550e8400-e29b-41d4-a716-446655440000"
  },
  "empresa": {
    "empresa_id": "550e8400-e29b-41d4-a716-446655440000",
    "nombre": "TechCorp Inc",
    "email": "careers@techcorp.com"
  }
}
```

**Error Responses**:
- `404 Not Found`: Application not found
- `400 Bad Request`: Invalid status value

---

## Vacantes (Job Openings) Endpoints

Base URL: `/api/puesto`

### 1. Create Job Opening

**Endpoint**: `POST /puesto/`

**Purpose**: Create a new vacancy for the authenticated company

**Request Body**:
```json
{
  "empresa_id": "550e8400-e29b-41d4-a716-446655440000",
  "titulo": "Desarrollador Full Stack Senior",
  "descripcion": "Buscamos un desarrollador con experiencia en React y Node.js para unirse a nuestro equipo",
  "ubicacion": "Ciudad de México",
  "salario_min": 25000,
  "salario_max": 35000,
  "moneda": "PEN",
  "tipo_contrato": "tiempo_completo",
  "requisitos": [
    {
      "tipo": "experiencia",
      "descripcion": "5 años de experiencia en desarrollo full stack",
      "es_obligatorio": true
    },
    {
      "tipo": "habilidad",
      "descripcion": "Dominio de React y Node.js",
      "es_obligatorio": true
    }
  ]
}
```

**Parameters**:
- `empresa_id` (string, required): ID of the company posting the job
- `titulo` (string, required): Job title
- `descripcion` (string, required): Detailed job description
- `ubicacion` (string, required): Job location
- `salario_min` (number, optional): Minimum salary offered
- `salario_max` (number, optional): Maximum salary offered
- `moneda` (string, optional): Salary currency - default: PEN
- `tipo_contrato` (string, required): Contract type - Valid values: tiempo_completo, medio_tiempo, temporal, freelance, practicas
- `requisitos` (array, optional): List of requirements with type, description, and es_obligatorio flag

**Response** (201 Created):
```json
{
  "puesto_id": "660e8400-e29b-41d4-a716-446655440001",
  "empresa_id": "550e8400-e29b-41d4-a716-446655440000",
  "titulo": "Desarrollador Full Stack Senior",
  "descripcion": "Buscamos un desarrollador con experiencia en React y Node.js para unirse a nuestro equipo",
  "ubicacion": "Ciudad de México",
  "salario_min": 25000,
  "salario_max": 35000,
  "moneda": "PEN",
  "tipo_contrato": "tiempo_completo",
  "fecha_publicacion": "2025-11-30T10:30:00",
  "fecha_cierre": null,
  "estado": "abierto",
  "requisitos": [
    {
      "tipo": "experiencia",
      "descripcion": "5 años de experiencia en desarrollo full stack",
      "es_obligatorio": true
    },
    {
      "tipo": "habilidad",
      "descripcion": "Dominio de React y Node.js",
      "es_obligatorio": true
    }
  ]
}
```

**Error Responses**:
- `400 Bad Request`: Invalid data

---

### 2. Get Job Opening

**Endpoint**: `GET /puesto/{puesto_id}`

**Purpose**: Retrieve details of a specific vacancy

**Path Parameters**:
- `puesto_id` (string, required): ID of the vacancy

**Response** (200 OK):
```json
{
  "puesto_id": "660e8400-e29b-41d4-a716-446655440001",
  "empresa_id": "550e8400-e29b-41d4-a716-446655440000",
  "titulo": "Desarrollador Full Stack Senior",
  "descripcion": "Buscamos un desarrollador con experiencia en React y Node.js para unirse a nuestro equipo",
  "ubicacion": "Ciudad de México",
  "salario_min": 25000,
  "salario_max": 35000,
  "moneda": "PEN",
  "tipo_contrato": "tiempo_completo",
  "fecha_publicacion": "2025-11-30T10:30:00",
  "fecha_cierre": null,
  "estado": "abierto",
  "requisitos": [
    {
      "tipo": "experiencia",
      "descripcion": "5 años de experiencia en desarrollo full stack",
      "es_obligatorio": true
    }
  ]
}
```

**Error Responses**:
- `404 Not Found`: Job position not found

---

### 3. List Job Openings

**Endpoint**: `GET /puesto/`

**Purpose**: List vacancies allowed for the authenticated role

**Query Parameters**:
- `empresa_id` (string, optional): Filter by company ID
- `estado` (string, optional): Filter by status - Valid values: abierto, cerrado

**Response** (200 OK):
```json
[
  {
    "puesto_id": "660e8400-e29b-41d4-a716-446655440001",
    "empresa_id": "550e8400-e29b-41d4-a716-446655440000",
    "titulo": "Desarrollador Full Stack Senior",
    "descripcion": "Buscamos un desarrollador con experiencia en React y Node.js para unirse a nuestro equipo",
    "ubicacion": "Ciudad de México",
    "salario_min": 25000,
    "salario_max": 35000,
    "moneda": "PEN",
    "tipo_contrato": "tiempo_completo",
    "fecha_publicacion": "2025-11-30T10:30:00",
    "fecha_cierre": null,
    "estado": "abierto",
    "requisitos": []
  }
]
```

**Error Responses**:
- `400 Bad Request`: Invalid filter parameters

---

### 4. Update Job Opening

**Endpoint**: `PUT /puesto/{puesto_id}`

**Purpose**: Update a vacancy owned by the authenticated company

**Path Parameters**:
- `puesto_id` (string, required): ID of the vacancy

**Request Body** (all fields optional):
```json
{
  "titulo": "Desarrollador Full Stack Senior (Updated)",
  "descripcion": "Updated description",
  "ubicacion": "Guadalajara",
  "salario_min": 28000,
  "salario_max": 38000,
  "moneda": "PEN",
  "tipo_contrato": "tiempo_completo",
  "requisitos": []
}
```

An omitted salary field keeps its current value; an explicit `null` removes
that minimum or maximum limit.

**Response** (200 OK):
```json
{
  "puesto_id": "660e8400-e29b-41d4-a716-446655440001",
  "empresa_id": "550e8400-e29b-41d4-a716-446655440000",
  "titulo": "Desarrollador Full Stack Senior (Updated)",
  "descripcion": "Updated description",
  "ubicacion": "Guadalajara",
  "salario_min": 28000,
  "salario_max": 38000,
  "moneda": "PEN",
  "tipo_contrato": "tiempo_completo",
  "fecha_publicacion": "2025-11-30T10:30:00",
  "fecha_cierre": null,
  "estado": "abierto",
  "requisitos": []
}
```

**Error Responses**:
- `404 Not Found`: Job position not found
- `400 Bad Request`: Invalid data

---

### 5. Change Job Opening Status

**Endpoint**: `PATCH /puesto/{puesto_id}/estado`

**Purpose**: Change the status of a vacancy between open and closed

**Path Parameters**:
- `puesto_id` (string, required): ID of the vacancy

**Request Body**:
```json
{
  "nuevo_estado": "cerrado"
}
```

**Parameters**:
- `nuevo_estado` (string, required): New status - Valid values: abierto, cerrado

**Response** (200 OK):
```json
{
  "puesto_id": "660e8400-e29b-41d4-a716-446655440001",
  "empresa_id": "550e8400-e29b-41d4-a716-446655440000",
  "titulo": "Desarrollador Full Stack Senior",
  "descripcion": "Buscamos un desarrollador con experiencia en React y Node.js para unirse a nuestro equipo",
  "ubicacion": "Ciudad de México",
  "salario_min": 25000,
  "salario_max": 35000,
  "moneda": "PEN",
  "tipo_contrato": "tiempo_completo",
  "fecha_publicacion": "2025-11-30T10:30:00",
  "fecha_cierre": "2025-11-30T16:00:00",
  "estado": "cerrado",
  "requisitos": []
}
```

**Error Responses**:
- `404 Not Found`: Job position not found
- `400 Bad Request`: Invalid status value

---

## Mensajería (Contact/Feedback) Endpoints

Base URL: `/api/contacto`

**Note**: Most contact endpoints are temporarily disabled (501 Not Implemented). Only feedback endpoint is available.

### 1. Send Feedback

**Endpoint**: `POST /contacto/feedback`

**Purpose**: Send feedback about a job application

**Request Body**:
```json
{
  "postulacion_id": "770e8400-e29b-41d4-a716-446655440002",
  "empresa_id": "550e8400-e29b-41d4-a716-446655440000",
  "cuenta_id": "550e8400-e29b-41d4-a716-446655440001",
  "tipo_feedback": "rechazo",
  "mensaje_texto": "Gracias por tu interés, pero hemos seleccionado a otro candidato",
  "motivo_rechazo": "Experiencia insuficiente"
}
```

**Parameters**:
- `postulacion_id` (string, required): ID of the application
- `empresa_id` (string, required): ID of the company
- `cuenta_id` (string, required): ID of the account sending feedback
- `tipo_feedback` (string, required): Feedback type - Valid values: aprobacion, rechazo, comentario, otro
- `mensaje_texto` (string, optional): Feedback message
- `motivo_rechazo` (string, optional): Reason for rejection

**Response** (201 Created):
```json
{
  "feedback_id": "990e8400-e29b-41d4-a716-446655440004",
  "postulacion_id": "770e8400-e29b-41d4-a716-446655440002",
  "tipo_feedback": "rechazo",
  "mensaje": "Gracias por tu interés, pero hemos seleccionado a otro candidato",
  "fecha_envio": "2025-11-30T16:45:00"
}
```

**Error Responses**:
- `400 Bad Request`: Invalid data

---

### Disabled Endpoints (501 Not Implemented)

The following endpoints are currently disabled:

- `POST /contacto/` - Create contact
- `GET /contacto/{contacto_id}` - Get contact
- `GET /contacto/` - List contacts
- `PATCH /contacto/{contacto_id}` - Update contact
- `PATCH /contacto/{contacto_id}/leido` - Mark contact as read
- `GET /contacto/feedback/{feedback_id}` - Get feedback

---

## Métricas (Metrics) Endpoints

Base URL: `/api/metricas`

### 1. Get Metrics Summary

**Endpoint**: `GET /metricas/resumen/{cuenta_id}`

**Purpose**: Get a summary of all metrics for a specific account (calculated in real-time)

**Path Parameters**:
- `cuenta_id` (UUID, required): Account ID

**Response** (200 OK):
```json
{
  "cuenta_id": "550e8400-e29b-41d4-a716-446655440000",
  "total_postulaciones": 15,
  "total_entrevistas": 3,
  "total_exitos": 2,
  "total_rechazos": 10,
  "tasa_exito": 13.33
}
```

**Error Responses**:
- `404 Not Found`: No metrics found for the account
- `500 Internal Server Error`: Error calculating metrics

---

### 2. List Achievements

**Endpoint**: `GET /metricas/logros/{cuenta_id}`

**Purpose**: List all achievements obtained by a specific account

**Path Parameters**:
- `cuenta_id` (UUID, required): Account ID

**Response** (200 OK):
```json
[
  {
    "id_logro": "logro_001",
    "nombre_logro": "Primer Éxito",
    "umbral": 1,
    "fecha_obtencion": "2025-11-30T14:30:00"
  },
  {
    "id_logro": "logro_005",
    "nombre_logro": "Cinco Postulaciones",
    "umbral": 5,
    "fecha_obtencion": "2025-11-25T10:15:00"
  }
]
```

**Error Responses**:
- `500 Internal Server Error`: Error retrieving achievements

---

### 3. Recalculate Metrics

**Endpoint**: `GET /metricas/recalcular/{cuenta_id}`

**Purpose**: Force recalculation of all metrics for a specific account

**Path Parameters**:
- `cuenta_id` (UUID, required): Account ID

**Response** (200 OK):
```json
{
  "cuenta_id": "550e8400-e29b-41d4-a716-446655440000",
  "total_postulaciones": 15,
  "total_entrevistas": 3,
  "total_exitos": 2,
  "total_rechazos": 10,
  "tasa_exito": 13.33
}
```

**Error Responses**:
- `500 Internal Server Error`: Error recalculating metrics

---

### 4. Get Accepted Applications Counter

**Endpoint**: `GET /metricas/contadores/ofertas/{postulante_id}`

**Purpose**: Get the count of accepted applications for the authenticated applicant

**Path Parameters**:
- `postulante_id` (UUID, required): Applicant ID

**Response** (200 OK):
```json
{
  "postulante_id": "550e8400-e29b-41d4-a716-446655440000",
  "total": 2
}
```

**Error Responses**:
- `500 Internal Server Error`: Error retrieving counter

---

### 5. Get Interviews Counter

**Endpoint**: `GET /metricas/contadores/entrevistas/{postulante_id}`

**Purpose**: Get the count of interviews obtained for a specific applicant

**Path Parameters**:
- `postulante_id` (UUID, required): Applicant ID

**Response** (200 OK):
```json
{
  "postulante_id": "550e8400-e29b-41d4-a716-446655440000",
  "total": 3
}
```

**Error Responses**:
- `500 Internal Server Error`: Error retrieving counter

---

### 6. Get Rejections Counter

**Endpoint**: `GET /metricas/contadores/rechazos/{postulante_id}`

**Purpose**: Get the count of rejections accumulated for a specific applicant

**Path Parameters**:
- `postulante_id` (UUID, required): Applicant ID

**Response** (200 OK):
```json
{
  "postulante_id": "550e8400-e29b-41d4-a716-446655440000",
  "total": 10
}
```

**Error Responses**:
- `500 Internal Server Error`: Error retrieving counter

---

## Error Handling

All errors follow a standard format:

**Error Response** (400/401/404/500):
```json
{
  "detail": "Descriptive error message"
}
```

### Common HTTP Status Codes

| Status Code | Meaning |
|------------|---------|
| 200 | OK - Request successful |
| 201 | Created - Resource successfully created |
| 400 | Bad Request - Invalid input data |
| 401 | Unauthorized - Authentication failed |
| 404 | Not Found - Resource not found |
| 500 | Internal Server Error - Server error |
| 501 | Not Implemented - Feature not available |

---

## Authentication

### JWT Token Usage

Most endpoints (except IAM endpoints) require authentication via JWT tokens.

**Header**:
```
Authorization: Bearer {access_token}
```

### Token Structure

- **Access Token**: Short-lived token (30 minutes by default) for API requests
- **Refresh Token**: Long-lived token (7 days) for obtaining new access tokens

### Example Request with Auth

```bash
curl -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
     https://backend-ufl2-c1kdvh50n-glitter22s-projects.vercel.app/api/iam/cuenta/550e8400-e29b-41d4-a716-446655440000
```

---

## Data Types Reference

### UUID
UUID format: `550e8400-e29b-41d4-a716-446655440000`

### DateTime
ISO 8601 format: `2025-11-30T10:30:00`

### Enums

**Application Status**:
- `pendiente` - Pending
- `en_revision` - Under review
- `rechazado` - Rejected
- `aceptado` - Accepted
- `entrevista` - Interview

**Vacancy Status**:
- `abierto` - Open
- `cerrado` - Closed

**Contract Type**:
- `tiempo_completo` - Full-time
- `medio_tiempo` - Part-time
- `temporal` - Temporary
- `freelance` - Freelance
- `practicas` - Internship

**Message Type**:
- `solicitud_info` - Information request
- `feedback` - Selection feedback
- `actualizacion` - Conversation message

**Feedback Type**:
- `aprobacion` - Approval
- `rechazo` - Rejection
- `comentario` - Comment
- `otro` - Other

**User Role**:
- `postulante` - Job applicant
- `empresa` - Company

---

## Usage Tips for Flutter Integration

1. **Store tokens securely**: Use secure storage packages like `flutter_secure_storage`
2. **Handle token refresh**: Automatically refresh access tokens before expiry
3. **Error handling**: Implement proper error handling for all API calls
4. **Loading states**: Add loading indicators during API requests
5. **Validation**: Validate input before sending to API
6. **Network handling**: Handle network errors gracefully

---

## Example Flutter Integration

```dart
// Login example
final response = await http.post(
  Uri.parse('https://backend-ufl2-c1kdvh50n-glitter22s-projects.vercel.app/api/iam/login'),
  headers: {'Content-Type': 'application/json'},
  body: jsonEncode({
    'email': 'user@example.com',
    'password': 'SecurePass123!',
  }),
);

if (response.statusCode == 200) {
  final data = jsonDecode(response.body);
  final accessToken = data['access_token'];
  // Store token securely
} else {
  // Handle error
}

// Authenticated request example
final response = await http.get(
  Uri.parse('https://backend-ufl2-c1kdvh50n-glitter22s-projects.vercel.app/api/iam/cuenta/$cuentaId'),
  headers: {
    'Authorization': 'Bearer $accessToken',
    'Content-Type': 'application/json',
  },
);
```

---

**Last Updated**: November 30, 2025
**API Version**: 1.0
