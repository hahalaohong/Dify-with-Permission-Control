export interface MemberPermissionSummary {
  id: string
  name: string
  email: string
  avatar: string | null
  role: string
  dataset_count: number
  app_count: number
}

export interface PermissionOverviewResponse {
  members: MemberPermissionSummary[]
  total_datasets: number
  total_apps: number
}

export interface ResourcePermission {
  id: string
  name: string
  permission: 'only_me' | 'all_team_members' | 'partial_members'
  created_by: string | null
  has_access: boolean
  is_partial: boolean
}

export interface MemberPermissionDetail {
  member: {
    id: string
    name: string
    email: string
    avatar: string | null
  }
  datasets: ResourcePermission[]
  apps: ResourcePermission[]
  accessible_dataset_ids: string[]
  accessible_app_ids: string[]
}

export interface ResourceItem {
  id: string
  name: string
  permission: 'only_me' | 'all_team_members' | 'partial_members'
}

export interface PermissionResourcesResponse {
  datasets: ResourceItem[]
  apps: ResourceItem[]
}

export interface UpdateMemberPermissionsPayload {
  dataset_ids: string[]
  app_ids: string[]
}
