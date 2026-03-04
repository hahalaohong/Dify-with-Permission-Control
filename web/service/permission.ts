import type {
  MemberPermissionDetail,
  PermissionOverviewResponse,
  PermissionResourcesResponse,
  UpdateMemberPermissionsPayload,
} from '@/models/permission'
import { get, put } from './base'

export const fetchPermissionOverview = (): Promise<PermissionOverviewResponse> => {
  return get<PermissionOverviewResponse>('/workspaces/current/permissions')
}

export const fetchMemberPermissions = (memberId: string): Promise<MemberPermissionDetail> => {
  return get<MemberPermissionDetail>(`/workspaces/current/permissions/members/${memberId}`)
}

export const updateMemberPermissions = (
  memberId: string,
  data: UpdateMemberPermissionsPayload,
): Promise<{ message: string }> => {
  return put<{ message: string }>(`/workspaces/current/permissions/members/${memberId}`, { body: data })
}

export const fetchPermissionResources = (): Promise<PermissionResourcesResponse> => {
  return get<PermissionResourcesResponse>('/workspaces/current/permissions/resources')
}

export const updateResourcePermissionMode = (
  resourceType: 'dataset' | 'app',
  resourceId: string,
  permission: string,
): Promise<{ message: string }> => {
  return put<{ message: string }>(`/workspaces/current/permissions/resources/${resourceType}/${resourceId}`, {
    body: { permission },
  })
}
