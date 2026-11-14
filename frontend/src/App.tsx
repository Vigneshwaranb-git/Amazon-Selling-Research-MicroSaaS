import type { ReactNode } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AuthProvider } from '@/context/AuthContext'
import { ProtectedRoute } from '@/components/ProtectedRoute'
import LoginPage from '@/pages/LoginPage'
import RegisterPage from '@/pages/RegisterPage'
import AuthCallbackPage from '@/pages/AuthCallbackPage'
import ForgotPasswordPage from '@/pages/ForgotPasswordPage'
import ResetPasswordPage from '@/pages/ResetPasswordPage'
import ProfilePage from '@/pages/ProfilePage'
import DashboardPage from '@/pages/DashboardPage'
import ProductDetailPage from '@/pages/ProductDetailPage'
import TrackingListsPage from '@/pages/TrackingListsPage'
import CalculatorPage from '@/pages/CalculatorPage'
import SavedScenariosPage from '@/pages/SavedScenariosPage'
import PricingPage from '@/pages/PricingPage'
import BillingPage from '@/pages/BillingPage'
import ReviewsPage from '@/pages/ReviewsPage'
import AnalyticsPage from '@/pages/AnalyticsPage'
import SettingsPage from '@/pages/SettingsPage'
import AdminDashboardPage from '@/pages/AdminDashboardPage'
import AdminUsersPage from '@/pages/AdminUsersPage'
import NotFoundPage from '@/pages/NotFoundPage'

const guard = (el: ReactNode, adminOnly = false) => (
  <ProtectedRoute adminOnly={adminOnly}>{el}</ProtectedRoute>
)

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route path="/auth/callback" element={<AuthCallbackPage />} />
          <Route path="/forgot-password" element={<ForgotPasswordPage />} />
          <Route path="/reset-password" element={<ResetPasswordPage />} />
          <Route path="/pricing" element={<PricingPage />} />
          <Route path="/profile" element={guard(<ProfilePage />)} />
          <Route path="/dashboard" element={guard(<DashboardPage />)} />
          <Route path="/products/:asin" element={guard(<ProductDetailPage />)} />
          <Route path="/tracking-lists" element={guard(<TrackingListsPage />)} />
          <Route path="/calculator" element={guard(<CalculatorPage />)} />
          <Route path="/calculator/saved" element={guard(<SavedScenariosPage />)} />
          <Route path="/settings/billing" element={guard(<BillingPage />)} />
          <Route path="/reviews/:asin" element={guard(<ReviewsPage />)} />
          <Route path="/analytics" element={guard(<AnalyticsPage />)} />
          <Route path="/settings" element={guard(<SettingsPage />)} />
          <Route path="/admin" element={guard(<AdminDashboardPage />, true)} />
          <Route path="/admin/users" element={guard(<AdminUsersPage />, true)} />
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}
