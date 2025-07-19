// API Client for Euro AIP Airport Explorer
class APIClient {
    constructor(baseURL = '') {
        this.baseURL = baseURL;
    }

    async request(endpoint, options = {}) {
        const url = `${this.baseURL}${endpoint}`;
        const config = {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            ...options
        };

        try {
            const response = await fetch(url, config);
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            return await response.json();
        } catch (error) {
            console.error('API request failed:', error);
            throw error;
        }
    }

    // Airport endpoints
    async getAirports(filters = {}) {
        const params = new URLSearchParams();
        
        if (filters.country) params.append('country', filters.country);
        if (filters.has_procedures === true) params.append('has_procedures', 'true');
        if (filters.has_hard_runway === true) params.append('has_hard_runway', 'true');
        if (filters.has_aip_data === true) params.append('has_aip_data', 'true');
        if (filters.point_of_entry === true) params.append('point_of_entry', 'true');
        // New AIP field filters
        if (filters.aip_field) params.append('aip_field', filters.aip_field);
        if (filters.aip_value) params.append('aip_value', filters.aip_value);
        if (filters.aip_operator) params.append('aip_operator', filters.aip_operator);
        if (filters.max_airports) params.append('limit', filters.max_airports);
        if (filters.offset) params.append('offset', filters.offset);

        const queryString = params.toString();
        const endpoint = `/api/airports/${queryString ? '?' + queryString : ''}`;
        
        return this.request(endpoint);
    }

    async getAirportDetail(icao) {
        return this.request(`/api/airports/${icao}`);
    }

    async getAirportAIPEntries(icao, filters = {}) {
        const params = new URLSearchParams();
        
        if (filters.section) params.append('section', filters.section);
        if (filters.std_field) params.append('std_field', filters.std_field);

        const queryString = params.toString();
        const endpoint = `/api/airports/${icao}/aip-entries${queryString ? '?' + queryString : ''}`;
        
        return this.request(endpoint);
    }

    async getAirportProcedures(icao, filters = {}) {
        const params = new URLSearchParams();
        
        if (filters.procedure_type) params.append('procedure_type', filters.procedure_type);
        if (filters.runway) params.append('runway', filters.runway);

        const queryString = params.toString();
        const endpoint = `/api/airports/${icao}/procedures${queryString ? '?' + queryString : ''}`;
        
        return this.request(endpoint);
    }

    async getAirportRunways(icao) {
        return this.request(`/api/airports/${icao}/runways`);
    }

    async getAirportProcedureLines(icao, distance_nm = 10.0) {
        return this.request(`/api/airports/${icao}/procedure-lines?distance_nm=${distance_nm}`);
    }

    async getBulkProcedureLines(airports, distance_nm = 10.0) {
        const requestBody = {
            airports: airports,
            distance_nm: distance_nm
        };
        
        console.log('getBulkProcedureLines request body:', requestBody);
        
        return this.request('/api/airports/bulk/procedure-lines', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(requestBody)
        });
    }

    async searchAirports(query, limit = 20) {
        return this.request(`/api/airports/search/${encodeURIComponent(query)}?limit=${limit}`);
    }

    async searchAirportsNearRoute(routeAirports, distanceNm = 50.0, filters = {}) {
        const airportsParam = routeAirports.join(',');
        const params = new URLSearchParams();
        params.append('airports', airportsParam);
        params.append('distance_nm', distanceNm.toString());
        
        // Add filter parameters
        if (filters.country) params.append('country', filters.country);
        if (filters.has_procedures === true) params.append('has_procedures', 'true');
        if (filters.has_aip_data === true) params.append('has_aip_data', 'true');
        if (filters.has_hard_runway === true) params.append('has_hard_runway', 'true');
        if (filters.point_of_entry === true) params.append('point_of_entry', 'true');
        // New AIP field filters
        if (filters.aip_field) params.append('aip_field', filters.aip_field);
        if (filters.aip_value) params.append('aip_value', filters.aip_value);
        if (filters.aip_operator) params.append('aip_operator', filters.aip_operator);
        
        return this.request(`/api/airports/route-search?${params.toString()}`);
    }

    // Filter endpoints
    async getAvailableCountries() {
        return this.request('/api/filters/countries');
    }

    async getAvailableProcedureTypes() {
        return this.request('/api/filters/procedure-types');
    }

    async getAvailableApproachTypes() {
        return this.request('/api/filters/approach-types');
    }

    async getAvailableAIPSections() {
        return this.request('/api/filters/aip-sections');
    }

    async getAvailableAIPFields() {
        return this.request('/api/filters/aip-fields');
    }

    async getAvailableSources() {
        return this.request('/api/filters/sources');
    }

    async getRunwayCharacteristics() {
        return this.request('/api/filters/runway-characteristics');
    }

    async getBorderCrossingStatistics() {
        return this.request('/api/filters/border-crossing');
    }

    async getAIPFilterPresets() {
        return this.request('/api/airports/aip-filter-presets');
    }

    async getAllFilters() {
        return this.request('/api/filters/all');
    }

    // Procedure endpoints
    async getProcedures(filters = {}) {
        const params = new URLSearchParams();
        
        if (filters.procedure_type) params.append('procedure_type', filters.procedure_type);
        if (filters.approach_type) params.append('approach_type', filters.approach_type);
        if (filters.runway) params.append('runway', filters.runway);
        if (filters.authority) params.append('authority', filters.authority);
        if (filters.source) params.append('source', filters.source);
        if (filters.airport) params.append('airport', filters.airport);
        if (filters.limit) params.append('limit', filters.limit);
        if (filters.offset) params.append('offset', filters.offset);

        const queryString = params.toString();
        const endpoint = `/api/procedures/${queryString ? '?' + queryString : ''}`;
        
        return this.request(endpoint);
    }

    async getApproaches(filters = {}) {
        const params = new URLSearchParams();
        
        if (filters.approach_type) params.append('approach_type', filters.approach_type);
        if (filters.runway) params.append('runway', filters.runway);
        if (filters.airport) params.append('airport', filters.airport);
        if (filters.limit) params.append('limit', filters.limit);

        const queryString = params.toString();
        const endpoint = `/api/procedures/approaches${queryString ? '?' + queryString : ''}`;
        
        return this.request(endpoint);
    }

    async getDepartures(filters = {}) {
        const params = new URLSearchParams();
        
        if (filters.runway) params.append('runway', filters.runway);
        if (filters.airport) params.append('airport', filters.airport);
        if (filters.limit) params.append('limit', filters.limit);

        const queryString = params.toString();
        const endpoint = `/api/procedures/departures${queryString ? '?' + queryString : ''}`;
        
        return this.request(endpoint);
    }

    async getArrivals(filters = {}) {
        const params = new URLSearchParams();
        
        if (filters.runway) params.append('runway', filters.runway);
        if (filters.airport) params.append('airport', filters.airport);
        if (filters.limit) params.append('limit', filters.limit);

        const queryString = params.toString();
        const endpoint = `/api/procedures/arrivals${queryString ? '?' + queryString : ''}`;
        
        return this.request(endpoint);
    }

    async getProceduresByRunway(airportIcao) {
        return this.request(`/api/procedures/by-runway/${airportIcao}`);
    }

    async getMostPreciseApproaches(airportIcao) {
        return this.request(`/api/procedures/most-precise/${airportIcao}`);
    }

    async getProcedureStatistics() {
        return this.request('/api/procedures/statistics');
    }

    // Statistics endpoints
    async getOverviewStatistics() {
        return this.request('/api/statistics/overview');
    }

    async getStatisticsByCountry() {
        return this.request('/api/statistics/by-country');
    }

    async getProcedureDistribution() {
        return this.request('/api/statistics/procedure-distribution');
    }

    async getAIPDataDistribution() {
        return this.request('/api/statistics/aip-data-distribution');
    }

    async getRunwayStatistics() {
        return this.request('/api/statistics/runway-statistics');
    }

    async getDataQualityStatistics() {
        return this.request('/api/statistics/data-quality');
    }

    // Health check
    async healthCheck() {
        return this.request('/health');
    }
}

// Create global API client instance
const api = new APIClient(); 