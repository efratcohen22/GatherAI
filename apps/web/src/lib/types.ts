export interface Organization { id: string; name: string; role: string | null }
export interface Me { id: string; email: string; display_name: string; organizations: Organization[] }
export interface Member { user_id: string; email: string; display_name: string; role: string; permissions: string[] }

export interface EventItem {
  id: string; organization_id: string; slug: string; name: string; description: string; event_type: string;
  location: string; timezone: string; start_at: string; end_at: string; capacity: number | null;
  registration_status: string; event_status: string; transportation_enabled: boolean; accommodation_enabled: boolean;
  archived_at: string | null; created_at: string;
}
export interface EventDetail extends EventItem { role: string; permissions: string[] }
export interface Alert { severity: "info" | "warning" | "critical"; code: string; title: string; link: string }
export interface Overview { metrics: Record<string, number | null>; alerts: Alert[] }
export interface Activity { id: string; action: string; entity_type: string; created_at: string }

export interface Participant {
  id: string; name: string; email: string | null; phone: string | null; registration_status: string;
  transportation_required: boolean; pickup_location: string | null; accommodation_required: boolean;
  dietary_preferences: string | null; notes: string | null; tags: string[]; ride_status: string; stay_status: string; open_requests: number;
}
export interface ParticipantPage { items: Participant[]; total: number; page: number; page_size: number }
export interface RequestItem { id: string; request_type: string; request_details: string; status: string }

export interface PersonRef { assignment_id: string; participant_id: string; name: string; status: string }
export interface Waiting { participant_id: string; name: string; registration_status: string; detail: string | null }
export interface Vehicle {
  id: string; driver_name: string | null; available_passenger_seats: number; departure_location: string;
  departure_at: string | null; notes: string | null; status: string; seats_remaining: number; passengers: PersonRef[];
}
export interface Transportation { vehicles: Vehicle[]; unassigned: Waiting[]; total_open_seats: number; shortage: number }
export interface Accommodation {
  id: string; host_name: string; host_contact: string | null; location: string; capacity: number;
  restrictions: string | null; status: string; beds_remaining: number; guests: PersonRef[];
}
export interface Accommodations { accommodations: Accommodation[]; unassigned: Waiting[]; total_open_beds: number; shortage: number }

export interface Task { id: string; title: string; description: string; status: string; priority: string; due_at: string | null }
export interface Message {
  id: string; participant_id: string | null; participant_name: string | null; channel: string; direction: string; content: string; status: string; created_at: string;
}

export interface Proposal {
  id: string; proposal_type: string; summary: string; rationale: string; approval_status: string; failure_reason: string | null;
  expires_at: string; created_at: string;
  proposed_payload: {
    assignments?: { participant_name: string; resource_label: string }[];
    unresolved?: { name: string; reason: string }[];
    tasks?: { title: string; priority: string }[];
  };
}
export interface ChatReply {
  conversation_id: string; reply: string; mode: "live" | "demo" | "unavailable"; tool_calls: { name: string; ok: boolean }[]; proposals: Proposal[];
}

export interface PublicEvent {
  slug: string; name: string; description: string; event_type: string; location: string; timezone: string; start_at: string; end_at: string;
  registration_open: boolean; availability: "open" | "limited" | "full"; transportation_enabled: boolean; accommodation_enabled: boolean;
}
export interface ManagedRegistration {
  event_name: string; name: string; registration_status: string; transportation_required: boolean; pickup_location: string | null;
  accommodation_required: boolean; dietary_preferences: string | null;
}
export interface SimConversation {
  id: string; event_id: string; phone: string | null; participant_name: string | null; step: string | null;
  messages: { role: string; content: string; created_at: string }[];
}
