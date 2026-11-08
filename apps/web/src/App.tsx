import { Link, Route, Routes } from "react-router-dom";
import { AppLayout, PublicLayout, RequireAuth } from "@/layouts/layouts";
import { ForgotPassword, Login, Signup } from "@/pages/auth";
import { EventOverview, Home, NewEvent } from "@/pages/events";
import { Accommodations, Transportation } from "@/pages/logistics";
import { Features, HowItWorks, Landing, Privacy, Terms } from "@/pages/marketing";
import { Assistant, Messages, Simulator, Tasks } from "@/pages/operations";
import { ManageRegistration, Register } from "@/pages/participant-public";
import { Participants } from "@/pages/participants";
import { AppSettings, EventSettings, Team } from "@/pages/settings";

function NotFound() {
  return (
    <div className="px-4 py-24 text-center">
      <h1 className="text-2xl font-semibold">Page not found</h1>
      <Link to="/" className="mt-3 inline-block text-primary-strong underline">Go home</Link>
    </div>
  );
}

export function App() {
  return (
    <Routes>
      <Route element={<PublicLayout />}>
        <Route index element={<Landing />} />
        <Route path="features" element={<Features />} />
        <Route path="how-it-works" element={<HowItWorks />} />
        <Route path="login" element={<Login />} />
        <Route path="signup" element={<Signup />} />
        <Route path="forgot-password" element={<ForgotPassword />} />
        <Route path="privacy" element={<Privacy />} />
        <Route path="terms" element={<Terms />} />
      </Route>
      <Route path="e/:slug" element={<Register />} />
      <Route path="r/:token" element={<ManageRegistration />} />
      <Route element={<RequireAuth />}>
        <Route path="app" element={<AppLayout />}>
          <Route index element={<Home />} />
          <Route path="events" element={<Home />} />
          <Route path="events/new" element={<NewEvent />} />
          <Route path="events/:eventId" element={<EventOverview />} />
          <Route path="events/:eventId/participants" element={<Participants />} />
          <Route path="events/:eventId/transportation" element={<Transportation />} />
          <Route path="events/:eventId/accommodations" element={<Accommodations />} />
          <Route path="events/:eventId/tasks" element={<Tasks />} />
          <Route path="events/:eventId/messages" element={<Messages />} />
          <Route path="events/:eventId/assistant" element={<Assistant />} />
          <Route path="events/:eventId/simulator" element={<Simulator />} />
          <Route path="events/:eventId/settings" element={<EventSettings />} />
          <Route path="team" element={<Team />} />
          <Route path="settings" element={<AppSettings />} />
        </Route>
      </Route>
      <Route path="*" element={<NotFound />} />
    </Routes>
  );
}
