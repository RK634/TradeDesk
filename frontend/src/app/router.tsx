import { createBrowserRouter, Navigate } from 'react-router-dom'
import { ProtectedRoute } from '@/features/auth/ProtectedRoute'
import { AppShell } from '@/components/layout/AppShell'
import { DashboardPage } from '@/pages/DashboardPage'
import { AcceptInvitationPage } from '@/pages/AcceptInvitationPage'
import { HomePage } from '@/pages/HomePage'
import { LoginPage } from '@/pages/LoginPage'
import { RegisterPage } from '@/pages/RegisterPage'
import { WorkspacePage } from '@/pages/WorkspacePage'
import { CustomersPage } from '@/pages/CustomersPage'
import { SuppliersPage } from '@/pages/SuppliersPage'
import { ProductsPage } from '@/pages/ProductsPage'
import { InventoryPage } from '@/pages/InventoryPage'
import { InventoryLocationsPage } from '@/pages/InventoryLocationsPage'
import { ImportsPage } from '@/pages/ImportsPage'
import { ExportsPage } from '@/pages/ExportsPage'
import { ShipmentsPage } from '@/pages/ShipmentsPage'
import { DocumentsPage } from '@/pages/DocumentsPage'
import { FinancePage } from '@/pages/FinancePage'
import { TasksPage } from '@/pages/TasksPage'
import { ApprovalsPage } from '@/pages/ApprovalsPage'
import { NotificationsPage } from '@/pages/NotificationsPage'
import { ReportsPage } from '@/pages/ReportsPage'
import { ArchivePage } from '@/pages/ArchivePage'

function NotFoundPage() {
  return (
    <main className="mx-auto flex min-h-screen max-w-xl flex-col items-start justify-center px-6">
      <p className="text-sm font-semibold text-primary">404 · Page not found</p>
      <h1 className="mt-2 text-3xl font-bold">That route does not exist.</h1>
      <p className="mt-3 text-muted-foreground">Check the address or return to the TradeDesk home page.</p>
      <a className="mt-6 text-sm font-semibold text-primary underline underline-offset-4" href="/">Return to home</a>
    </main>
  )
}

export const router = createBrowserRouter([
  { path: '/', element: <HomePage /> },
  { path: '/login', element: <LoginPage /> },
  { path: '/register', element: <RegisterPage /> },
  { path: '/accept-invitation', element: <AcceptInvitationPage /> },
  {
    path: '/app',
    element: <ProtectedRoute><AppShell /></ProtectedRoute>,
    children: [
      { index: true, element: <DashboardPage /> },
      { path: 'organization', element: <WorkspacePage embedded /> },
      { path: 'customers', element: <CustomersPage /> },
      { path: 'suppliers', element: <SuppliersPage /> },
      { path: 'products', element: <ProductsPage /> },
      { path: 'inventory', element: <InventoryPage /> },
      { path: 'locations', element: <InventoryLocationsPage /> },
      { path: 'imports', element: <ImportsPage /> },
      { path: 'exports', element: <ExportsPage /> },
      { path: 'shipments', element: <ShipmentsPage /> },
      { path: 'documents', element: <DocumentsPage /> },
      { path: 'invoices', element: <FinancePage /> },
      { path: 'payments', element: <FinancePage /> },
      { path: 'tasks', element: <TasksPage /> },
      { path: 'approvals', element: <ApprovalsPage /> },
      { path: 'notifications', element: <NotificationsPage /> },
      { path: 'reports', element: <ReportsPage /> },
      { path: 'archive', element: <ArchivePage /> },
      { path: '*', element: <Navigate to="/app" replace /> },
    ],
  },
  { path: '*', element: <NotFoundPage /> },
])
