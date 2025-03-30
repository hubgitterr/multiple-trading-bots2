import axios from 'axios';

// Determine the backend URL. Use environment variable if available, otherwise default to localhost.
const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

const apiClient = axios.create({
  baseURL: BACKEND_URL,
  headers: {
    'Content-Type': 'application/json',
    // Authorization header will be added per request where needed
  },
});

// Optional: Add interceptors for handling requests or responses globally
// apiClient.interceptors.request.use(async (config) => {
//   // Example: Get token from Supabase and add it to headers
//   // const { data: { session } } = await supabase.auth.getSession();
//   // const token = session?.access_token;
//   // if (token) {
//   //   config.headers.Authorization = `Bearer ${token}`;
//   // }
//   return config;
// });

// apiClient.interceptors.response.use(
//   (response) => response, // Pass through successful responses
//   (error) => {
//     // Handle errors globally (e.g., redirect on 401, show generic error message)
//     console.error('API Client Error:', error.response || error.message);
//     // Potentially trigger UI notification
//     return Promise.reject(error); // Reject the promise so calling code can handle specific errors
//   }
// );

export default apiClient;

// Simple fetcher function for use with SWR or manual fetching
export const fetcher = async (url: string, token?: string) => {
  const headers: Record<string, string> = {};
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  const res = await apiClient.get(url, { headers });
  return res.data;
};
