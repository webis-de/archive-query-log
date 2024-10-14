import axios from 'axios';

const BASE_URL = 'http://localhost:8000';

export async function fetchData(endpoint) {
  try {
    const response = await axios.get(`${BASE_URL}${endpoint}`);
    return response.data;
  } catch (error) {
    console.error(`Error fetching data from ${endpoint}:`, error.message);
    throw error;
  }
}