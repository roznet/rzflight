// Filter functionality for Euro AIP Airport Explorer
class FilterManager {
    constructor() {
        this.currentFilters = { point_of_entry: true }; // Default to border crossing airports
        this.availableFilters = {};
        this.airports = [];
        
        this.initEventListeners();
        this.updateResetZoomButton(); // Initialize button state
    }

    initEventListeners() {
        // Apply filters button
        document.getElementById('apply-filters').addEventListener('click', () => {
            this.applyFilters();
        });

        // Reset zoom button
        document.getElementById('reset-zoom').addEventListener('click', () => {
            this.resetZoom();
        });

        // Search input with debouncing
        const searchInput = document.getElementById('search-input');
        let searchTimeout;
        searchInput.addEventListener('input', (e) => {
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(() => {
                this.handleSearch(e.target.value);
            }, 300);
        });

        // Enter key in search
        searchInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                this.handleSearch(e.target.value);
            }
        });

        // Filter change events
        document.getElementById('country-filter').addEventListener('change', () => {
            this.updateFilters();
        });

        document.getElementById('approach-filter').addEventListener('change', () => {
            this.updateFilters();
        });

        document.getElementById('max-airports-filter').addEventListener('change', () => {
            this.updateFilters();
        });

        // Legend mode change
        document.getElementById('legend-mode-filter').addEventListener('change', () => {
            this.updateLegendMode();
        });

        // Checkbox events
        const checkboxes = ['has-procedures', 'has-aip-data', 'has-hard-runway', 'border-crossing-only'];
        checkboxes.forEach(id => {
            document.getElementById(id).addEventListener('change', () => {
                this.updateFilters();
            });
        });
    }

    async loadAvailableFilters() {
        try {
            this.availableFilters = await api.getAllFilters();
            this.populateFilterOptions();
        } catch (error) {
            console.error('Error loading filter options:', error);
        }
    }

    populateFilterOptions() {
        // Populate country filter
        const countrySelect = document.getElementById('country-filter');
        countrySelect.innerHTML = '<option value="">All Countries</option>';
        
        if (this.availableFilters.countries) {
            this.availableFilters.countries.forEach(country => {
                const option = document.createElement('option');
                option.value = country.code;
                option.textContent = `${country.code} (${country.count})`;
                countrySelect.appendChild(option);
            });
            
            // No default country - show all border crossing airports
        }



        // Populate approach type filter
        const approachSelect = document.getElementById('approach-filter');
        approachSelect.innerHTML = '<option value="">All Approaches</option>';
        
        if (this.availableFilters.approach_types) {
            this.availableFilters.approach_types.forEach(approach => {
                const option = document.createElement('option');
                option.value = approach.type;
                option.textContent = `${approach.type} (${approach.count})`;
                approachSelect.appendChild(option);
            });
        }
    }

    updateFilters() {
        this.currentFilters = {
            country: document.getElementById('country-filter').value,
            approach_type: document.getElementById('approach-filter').value,
            max_airports: parseInt(document.getElementById('max-airports-filter').value),
            has_procedures: document.getElementById('has-procedures').checked ? true : undefined,
            has_aip_data: document.getElementById('has-aip-data').checked ? true : undefined,
            has_hard_runway: document.getElementById('has-hard-runway').checked ? true : undefined,
            point_of_entry: document.getElementById('border-crossing-only').checked ? true : undefined
        };

        // Remove undefined values
        Object.keys(this.currentFilters).forEach(key => {
            if (this.currentFilters[key] === undefined) {
                delete this.currentFilters[key];
            }
        });
    }

    async applyFilters() {
        try {
            this.showLoading();
            
            // Update filters from UI
            this.updateFilters();
            
            // Check if we have an active route search
            if (this.currentRoute && this.currentRoute.airports) {
                console.log('applyFilters - Reapplying route search with new filters');
                // Reapply route search with current filters
                await this.handleRouteSearch(this.currentRoute.airports, true);
                return;
            }
            
            // Regular filter application (no active route)
            console.log('applyFilters - Applying regular filters');
            
            // Load airports with filters
            const airports = await api.getAirports({
                ...this.currentFilters
            });
            
            // Update map with filtered airports (preserve current view)
            this.updateMapWithAirports(airports, true);
            
            // Update statistics
            this.updateStatistics(airports);
            
            // Show success message
            this.showSuccess(`Applied filters: ${airports.length} airports found (view preserved)`);
            
        } catch (error) {
            console.error('Error applying filters:', error);
            this.showError('Error applying filters: ' + error.message);
        } finally {
            this.hideLoading();
        }
    }

    async handleSearch(query) {
        if (!query.trim()) {
            // If search is empty, apply current filters
            this.applyFilters();
            return;
        }

        try {
            this.showLoading();
            
            console.log('handleSearch - Input query:', query);
            
            // Check if this looks like a route search (space-separated ICAO codes)
            const routeAirports = this.parseRouteFromQuery(query);
            
            console.log('handleSearch - Route airports detected:', routeAirports);
            
            if (routeAirports && routeAirports.length >= 2) {
                // This is a route search
                console.log('handleSearch - Executing route search');
                await this.handleRouteSearch(routeAirports);
            } else {
                // This is a regular text search
                console.log('handleSearch - Executing regular text search');
                
                // Clear any current route since this is a regular search
                this.currentRoute = null;
                
                const searchResults = await api.searchAirports(query, 50);
                
                // Update map with search results (fit to bounds for better UX)
                this.updateMapWithAirports(searchResults, false);
                
                // Update statistics
                this.updateStatistics(searchResults);
                
                // Show search success message
                this.showSuccess(`Search results: ${searchResults.length} airports found`);
            }
            
        } catch (error) {
            console.error('Error searching airports:', error);
            this.showError('Error searching airports: ' + error.message);
        } finally {
            this.hideLoading();
        }
    }

    parseRouteFromQuery(query) {
        // Split by spaces and filter out empty strings
        const parts = query.trim().split(/\s+/).filter(part => part.length > 0);
        
        console.log('parseRouteFromQuery - Input query:', query);
        console.log('parseRouteFromQuery - Parts:', parts);
        
        // Check if all parts look like ICAO codes (4 letters, case insensitive)
        const icaoPattern = /^[A-Za-z]{4}$/;
        const allIcaoCodes = parts.every(part => icaoPattern.test(part));
        
        console.log('parseRouteFromQuery - All ICAO codes:', allIcaoCodes);
        console.log('parseRouteFromQuery - Parts length:', parts.length);
        
        if (allIcaoCodes && parts.length >= 2) {
            const result = parts.map(part => part.toUpperCase());
            console.log('parseRouteFromQuery - Returning route airports:', result);
            return result;
        }
        
        console.log('parseRouteFromQuery - Not a route, returning null');
        return null;
    }

    async handleRouteSearch(routeAirports, skipFilterUpdate = false) {
        try {
            // Get distance from UI or use default
            const distanceInput = document.getElementById('route-distance') || { value: '50' };
            const distanceNm = parseFloat(distanceInput.value) || 50.0;
            
            // Get current filter settings (unless already updated)
            if (!skipFilterUpdate) {
                this.updateFilters();
            }
            const currentFilters = this.currentFilters;
            
            console.log('handleRouteSearch - Current filters:', currentFilters);
            
            // Search for airports near the route with filters
            const routeResults = await api.searchAirportsNearRoute(routeAirports, distanceNm, currentFilters);
            
            // Extract airport data for unified handling
            const airports = routeResults.airports.map(item => ({
                ...item.airport,
                // Add route-specific data as custom properties
                _routeDistance: item.distance_nm,
                _closestSegment: item.closest_segment
            }));
            
            // Use the same unified airport handling as normal mode
            this.updateMapWithAirports(airports, false);
            
            // Display the route on the map (after airports are added)
            airportMap.displayRoute(routeAirports, distanceNm);
            
            // Update statistics
            this.updateStatistics(airports);
            
            // Show route search success message with filter info
            let message = `Route search: ${routeResults.airports_found} airports within ${distanceNm}nm of route ${routeAirports.join(' → ')}`;
            if (routeResults.total_nearby > routeResults.airports_found) {
                message += ` (filtered from ${routeResults.total_nearby} total nearby)`;
            }
            
            // Add filter information to the message
            const activeFilters = [];
            if (currentFilters.country) activeFilters.push(`Country: ${currentFilters.country}`);
            if (currentFilters.has_procedures) activeFilters.push('Has Procedures');
            if (currentFilters.has_aip_data) activeFilters.push('Has AIP Data');
            if (currentFilters.has_hard_runway) activeFilters.push('Has Hard Runway');
            if (currentFilters.point_of_entry) activeFilters.push('Border Crossing');
            
            if (activeFilters.length > 0) {
                message += ` | Filters: ${activeFilters.join(', ')}`;
            }
            
            this.showSuccess(message);
            
            // Store route information for potential future use
            this.currentRoute = {
                airports: routeAirports,
                distance_nm: distanceNm,
                filters: currentFilters,
                results: routeResults
            };
            
        } catch (error) {
            console.error('Error in route search:', error);
            this.showError('Error searching route: ' + error.message);
        }
    }

    updateMapWithAirports(airports, preserveView = false) {
        // Clear existing markers
        airportMap.clearMarkers();
        
        // Add new markers
        airports.forEach(airport => {
            airportMap.addAirport(airport);
        });
        
        // Only fit bounds if not preserving view (e.g., for search results)
        if (airports.length > 0 && !preserveView) {
            airportMap.fitBounds();
        }
        
        // Store current airports
        this.airports = airports;
        
        // Update reset zoom button state
        this.updateResetZoomButton();
        
        // If in procedure precision mode, load procedure lines in bulk
        const legendMode = document.getElementById('legend-mode-filter').value;
        if (legendMode === 'procedure-precision') {
            console.log('In procedure precision mode, loading procedure lines in bulk...');
            airportMap.loadBulkProcedureLines(airports);
        }
    }

    updateStatistics(airports) {
        const totalAirports = airports.length;
        const airportsWithProcedures = airports.filter(a => a.has_procedures).length;
        const borderCrossing = airports.filter(a => a.point_of_entry).length;
        const totalProcedures = airports.reduce((sum, a) => sum + a.procedure_count, 0);

        // Update statistics cards
        document.getElementById('total-airports').textContent = totalAirports.toLocaleString();
        document.getElementById('airports-with-procedures').textContent = airportsWithProcedures.toLocaleString();
        document.getElementById('border-crossing').textContent = borderCrossing.toLocaleString();
        document.getElementById('total-procedures').textContent = totalProcedures.toLocaleString();
    }

    showLoading() {
        document.getElementById('loading').style.display = 'block';
        document.getElementById('apply-filters').disabled = true;
        document.getElementById('apply-filters').innerHTML = '<i class="fas fa-spinner fa-spin"></i> Loading...';
    }

    hideLoading() {
        document.getElementById('loading').style.display = 'none';
        document.getElementById('apply-filters').disabled = false;
        document.getElementById('apply-filters').innerHTML = '<i class="fas fa-search"></i> Apply Filters';
    }

    showSuccess(message) {
        // Create a temporary success alert
        const alertDiv = document.createElement('div');
        alertDiv.className = 'alert alert-success alert-dismissible fade show position-fixed';
        alertDiv.style.cssText = 'top: 20px; right: 20px; z-index: 9999; min-width: 300px;';
        alertDiv.innerHTML = `
            <i class="fas fa-check-circle"></i> ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        
        document.body.appendChild(alertDiv);
        
        // Auto-remove after 3 seconds
        setTimeout(() => {
            if (alertDiv.parentNode) {
                alertDiv.remove();
            }
        }, 3000);
    }

    showError(message) {
        // Create a temporary error alert
        const alertDiv = document.createElement('div');
        alertDiv.className = 'alert alert-danger alert-dismissible fade show position-fixed';
        alertDiv.style.cssText = 'top: 20px; right: 20px; z-index: 9999; min-width: 300px;';
        alertDiv.innerHTML = `
            <i class="fas fa-exclamation-triangle"></i> ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        
        document.body.appendChild(alertDiv);
        
        // Auto-remove after 5 seconds
        setTimeout(() => {
            if (alertDiv.parentNode) {
                alertDiv.remove();
            }
        }, 5000);
    }

    // Get current filter state
    getCurrentFilters() {
        return { ...this.currentFilters };
    }

    // Set default border crossing filter
    setDefaultBorderCrossingFilter() {
        // Set the border crossing checkbox to checked
        document.getElementById('border-crossing-only').checked = true;
        
        // Update filters to include border crossing
        this.currentFilters = { point_of_entry: true };
        
        // Apply the filter with initial fit bounds
        this.applyFiltersInitial();
    }

    async applyFiltersInitial() {
        try {
            this.showLoading();
            
            // Update filters from UI
            this.updateFilters();
            
            // Load airports with filters
            const airports = await api.getAirports({
                ...this.currentFilters
            });
            
            // Update map with filtered airports (fit bounds for initial load)
            this.updateMapWithAirports(airports, false);
            
            // Update statistics
            this.updateStatistics(airports);
            
        } catch (error) {
            console.error('Error applying initial filters:', error);
            this.showError('Error applying initial filters: ' + error.message);
        } finally {
            this.hideLoading();
        }
    }

    // Clear all filters
    clearFilters() {
        document.getElementById('country-filter').value = '';
        document.getElementById('approach-filter').value = '';
        document.getElementById('max-airports-filter').value = '1000';
        document.getElementById('search-input').value = '';
        
        // Uncheck all checkboxes
        ['has-procedures', 'has-aip-data', 'has-hard-runway', 'border-crossing-only'].forEach(id => {
            document.getElementById(id).checked = false;
        });
        
        this.currentFilters = {};
    }

    // Update reset zoom button state
    updateResetZoomButton() {
        const resetButton = document.getElementById('reset-zoom');
        if (resetButton) {
            resetButton.disabled = this.airports.length === 0;
        }
    }

    // Reset zoom to fit all current markers
    resetZoom() {
        if (this.airports.length > 0) {
            airportMap.fitBounds();
            this.showSuccess(`Reset zoom to show all ${this.airports.length} airports`);
        } else {
            this.showError('No airports to zoom to');
        }
    }

    updateLegendMode() {
        const legendMode = document.getElementById('legend-mode-filter').value;
        console.log(`Legend mode changed to: ${legendMode}`);
        
        if (airportMap) {
            airportMap.setLegendMode(legendMode);
            airportMap.updateLegend();
            
            // Update the map markers to reflect the new legend mode
            if (this.airports && this.airports.length > 0) {
                // Clear and re-add markers to update their appearance
                airportMap.clearMarkers();
                this.airports.forEach(airport => {
                    airportMap.addAirport(airport);
                });
                
                // If switching to procedure precision mode, load procedure lines in bulk
                if (legendMode === 'procedure-precision') {
                    console.log('Switching to procedure precision mode, loading procedure lines in bulk...');
                    airportMap.loadBulkProcedureLines(this.airports);
                }
            }
        }
    }

    // Export current filter state
    exportFilters() {
        return {
            filters: this.currentFilters,
            airports: this.airports.length,
            timestamp: new Date().toISOString()
        };
    }
}

// Create global filter manager instance
let filterManager; 