/**
 * API client for backend communication
 */

const API_BASE = '/api';

// Get CSRF token from cookie
function getCsrfToken(): string | null {
	const name = 'csrftoken';
	const cookies = document.cookie.split(';');
	for (const cookie of cookies) {
		const [cookieName, cookieValue] = cookie.trim().split('=');
		if (cookieName === name) {
			return cookieValue;
		}
	}
	return null;
}

export interface User {
	id: number;
	username: string;
	email: string;
	first_name: string;
	last_name: string;
}

export interface AuthStatus {
	authenticated: boolean;
	user?: User;
}

export interface PhotoFolder {
	id: number;
	name: string;
	event_name: string;
	nextcloud_folder_path: string;
	nextcloud_share_token: string;
	share_token: string;
	is_active: boolean;
	naming_format: string;
	jpeg_quality: number;
	readme_message: string;
	upload_url: string;
	nextcloud_share_url: string | null;
	upload_count?: number;
	created_at: string;
	updated_at: string;
}

export interface NamingFormat {
	value: string;
	label: string;
}

export interface UploadStatistic {
	id: number;
	uploader_ip: string;
	filename_original: string;
	filename_converted: string;
	file_size_original: number;
	file_size_converted: number;
	file_type: string;
	conversion_time_seconds: number;
	uploaded_at: string;
}

export interface FolderStatistics {
	total_uploads: number;
	total_size_original_bytes: number;
	total_size_converted_bytes: number;
	uploads_by_ip: Record<string, number>;
	recent_uploads: UploadStatistic[];
}

export interface FolderInfo {
	name: string;
	event_name: string;
	nextcloud_share_url: string | null;
	supported_image_formats: string[];
	supported_video_formats: string[];
	max_upload_size_mb: number;
}

export interface UploadResult {
	success: boolean;
	task_id: string;
	message: string;
	filename: string;
	nextcloud_share_url: string | null;
}

export interface TaskStatus {
	task_id: string;
	status: 'PENDING' | 'STARTED' | 'SUCCESS' | 'FAILURE' | 'RETRY';
	result?: {
		success: boolean;
		filename: string;
		original_size: number;
		converted_size: number;
		conversion_time: number;
	};
	error?: string;
}

async function request<T>(url: string, options: RequestInit = {}): Promise<T> {
	const csrfToken = getCsrfToken();
	const headers: Record<string, string> = {
		'Content-Type': 'application/json',
		...(options.headers as Record<string, string>)
	};
	
	// Add CSRF token for non-GET requests
	if (csrfToken && options.method && options.method !== 'GET') {
		headers['X-CSRFToken'] = csrfToken;
	}
	
	const response = await fetch(`${API_BASE}${url}`, {
		...options,
		credentials: 'include',
		headers
	});

	if (!response.ok) {
		const error = await response.json().catch(() => ({ error: 'Request failed' }));
		throw new Error(error.error || error.detail || 'Request failed');
	}

	return response.json();
}

// Auth API
export const auth = {
	status: () => request<AuthStatus>('/auth/status/'),
	logout: () =>
		request<{ success: boolean }>('/auth/logout/', {
			method: 'POST'
		}),
	config: () => request<{ nextcloud_url: string }>('/auth/config/')
};

// Folders API
export const folders = {
	list: () => request<PhotoFolder[]>('/folders/'),
	get: (id: number) => request<PhotoFolder>(`/folders/${id}/`),
	create: (data: Partial<PhotoFolder>) =>
		request<PhotoFolder>('/folders/', {
			method: 'POST',
			body: JSON.stringify(data)
		}),
	update: (id: number, data: Partial<PhotoFolder>) =>
		request<PhotoFolder>(`/folders/${id}/`, {
			method: 'PATCH',
			body: JSON.stringify(data)
		}),
	delete: (id: number) =>
		request<void>(`/folders/${id}/`, {
			method: 'DELETE'
		}),
	regenerateToken: (id: number) =>
		request<{ share_token: string; upload_url: string }>(`/folders/${id}/regenerate_token/`, {
			method: 'POST'
		}),
	regenerateNextcloudShare: (id: number) =>
		request<{ nextcloud_share_token: string; nextcloud_share_url: string }>(
			`/folders/${id}/regenerate_nextcloud_share/`,
			{ method: 'POST' }
		),
	statistics: (id: number) => request<FolderStatistics>(`/folders/${id}/statistics/`),
	namingFormats: () => request<NamingFormat[]>('/folders/naming_formats/')
};

// Upload API (public, no auth required)
export const upload = {
	folderInfo: async (shareToken: string): Promise<FolderInfo> => {
		const response = await fetch(`${API_BASE}/upload/${shareToken}/info/`);
		if (!response.ok) {
			const error = await response.json().catch(() => ({ error: 'Folder not found' }));
			throw new Error(error.error || 'Folder not found');
		}
		return response.json();
	},

	uploadFile: async (shareToken: string, file: File): Promise<UploadResult> => {
		const formData = new FormData();
		formData.append('file', file);

		const response = await fetch(`${API_BASE}/upload/${shareToken}/`, {
			method: 'POST',
			body: formData
		});

		if (!response.ok) {
			const error = await response.json().catch(() => ({ error: 'Upload failed' }));
			throw new Error(error.error || 'Upload failed');
		}

		return response.json();
	},

	taskStatus: async (taskId: string): Promise<TaskStatus> => {
		const response = await fetch(`${API_BASE}/upload/task/${taskId}/`);
		return response.json();
	}
};
