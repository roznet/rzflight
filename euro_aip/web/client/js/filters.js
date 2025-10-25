// Filter functionality for Euro AIP Airport Explorer
class FilterManager {
    constructor() {
        this.currentFilters = {};
        this.airports = [];
        this.currentRoute = null;
        this.autoApplyTimeout = null;
        this.aipPresets = [];
        this.aipFields = [];
        
        this.initEventListeners();
        this.loadAvailableFilters();
        this.loadAIPFilterPresets();
        this.loadAIPFields();
    }

    initEventListeners() {
        // Search input
        const searchInput = document.getElementById('search-input');
        searchInput.addEventListener('input', (e) => {
            this.handleSearch(e.target.value);
        });

        // Filter controls
        const filterControls = [
            'country-filter',
            'has-procedures',
            'has-aip-data', 
            'has-hard-runway',
            'border-crossing-only',
            'route-distance',
            'max-airports-filter'
        ];

        filterControls.forEach(id => {
            const element = document.getElementById(id);
            if (element) {
                element.addEventListener('change', () => {
                    this.autoApplyFilters();
                });
            }
        });

        // AIP field filter controls
        const aipFieldSelect = document.getElementById('aip-field-select');
        const aipOperatorSelect = document.getElementById('aip-operator-select');
        const aipValueInput = document.getElementById('aip-value-input');
        const clearAIPFilterBtn = document.getElementById('clear-aip-filter');
        const removeAIPFilterBtn = document.getElementById('remove-aip-filter');

        if (aipFieldSelect) {
            aipFieldSelect.addEventListener('change', () => {
                if (aipFieldSelect.value) {
                    this.applyCustomAIPFilter();
                }
            });
        }

        if (aipOperatorSelect) {
            aipOperatorSelect.addEventListener('change', () => {
                if (aipFieldSelect.value) {
                    this.applyCustomAIPFilter();
                }
            });
        }

        if (aipValueInput) {
            aipValueInput.addEventListener('input', () => {
                if (aipFieldSelect.value) {
                    this.applyCustomAIPFilter();
                }
            });
        }

        if (clearAIPFilterBtn) {
            clearAIPFilterBtn.addEventListener('click', () => {
                this.clearAIPFilter();
            });
        }

        if (removeAIPFilterBtn) {
            removeAIPFilterBtn.addEventListener('click', () => {
                this.clearAIPFilter();
            });
        }

        // Apply filters button
        const applyButton = document.getElementById('apply-filters');
        applyButton.addEventListener('click', () => {
            this.applyFilters();
        });

        // Reset zoom button
        const resetZoomButton = document.getElementById('reset-zoom');
        resetZoomButton.addEventListener('click', () => {
            this.resetZoom();
        });

        // Legend mode filter
        const legendModeFilter = document.getElementById('legend-mode-filter');
        legendModeFilter.addEventListener('change', () => {
            this.updateLegendMode();
        });
    }

    autoApplyFilters() {
        // Clear any existing timeout
        if (this.autoApplyTimeout) {
            clearTimeout(this.autoApplyTimeout);
        }
        
        // Debounce the auto-apply to prevent rapid successive API calls
        this.autoApplyTimeout = setTimeout(() => {
            this.applyFilters();
            // Update URL after applying filters
            this.updateURL();
        }, 500); // 500ms delay
        
        // Show immediate feedback that filters are being applied
        this.showFilterChangeIndicator();
    }

    showFilterChangeIndicator() {
        const applyButton = document.getElementById('apply-filters');
        const originalText = applyButton.innerHTML;
        
        // Show "Applying..." indicator
        applyButton.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Applying...';
        applyButton.disabled = true;
        
        // Reset after auto-apply completes (handled in applyFilters)
    }

    async loadAvailableFilters() {
        try {
            console.log('Loading available filters...');
            const filters = await api.getAllFilters();
            console.log('Received filters from API:', filters);
            this.populateFilterOptions(filters);
        } catch (error) {
            console.error('Error loading available filters:', error);
        }
    }

    async loadAIPFilterPresets() {
        try {
            this.aipPresets = await api.getAIPFilterPresets();
            this.populateAIPPresets();
        } catch (error) {
            console.error('Error loading AIP filter presets:', error);
        }
    }

    async loadAIPFields() {
        try {
            const fields = await api.getAvailableAIPFields();
            this.aipFields = fields;
            this.populateAIPFields();
        } catch (error) {
            console.error('Error loading AIP fields:', error);
        }
    }

    populateFilterOptions(filters) {
        console.log('populateFilterOptions called with:', filters);
        
        // Populate country filter
        const countrySelect = document.getElementById('country-filter');
        countrySelect.innerHTML = '<option value="">All Countries</option>';
        
        if (filters.countries) {
            console.log('Found countries:', filters.countries);
            filters.countries.forEach(country => {
                const option = document.createElement('option');
                option.value = country.code;
                option.textContent = `${country.name} (${country.count})`;
                countrySelect.appendChild(option);
            });
        } else {
            console.log('No countries found in filters');
        }
    }

    populateAIPPresets() {
        const presetsContainer = document.getElementById('aip-preset-buttons');
        presetsContainer.innerHTML = '';
        
        if (this.aipPresets) {
            this.aipPresets.forEach(preset => {
                const button = document.createElement('button');
                button.type = 'button';
                button.className = 'aip-preset-btn';
                button.dataset.presetId = preset.id;
                button.innerHTML = `
                    <span class="icon">${preset.icon}</span>
                    <span>${preset.name}</span>
                `;
                button.title = preset.description;
                
                button.addEventListener('click', () => {
                    this.applyAIPPreset(preset);
                });
                
                presetsContainer.appendChild(button);
            });
        }
    }

    populateAIPFields() {
        const fieldSelect = document.getElementById('aip-field-select');
        fieldSelect.innerHTML = '<option value="">Select AIP Field...</option>';
        
        if (this.aipFields) {
            this.aipFields.forEach(field => {
                const option = document.createElement('option');
                option.value = field.field;
                option.textContent = field.field;
                fieldSelect.appendChild(option);
            });
        }
    }

    updateFilters() {
        // Get current filter values
        const countrySelect = document.getElementById('country-filter');
        const maxAirportsSelect = document.getElementById('max-airports-filter');
        const hasProceduresCheckbox = document.getElementById('has-procedures');
        const hasAIPDataCheckbox = document.getElementById('has-aip-data');
        const hasHardRunwayCheckbox = document.getElementById('has-hard-runway');
        const borderCrossingCheckbox = document.getElementById('border-crossing-only');
        
        // Preserve AIP field filters before resetting
        const aipField = this.currentFilters.aip_field;
        const aipValue = this.currentFilters.aip_value;
        const aipOperator = this.currentFilters.aip_operator;
        
        // Update current filters - only include defined values
        this.currentFilters = {};
        
        if (countrySelect.value) {
            this.currentFilters.country = countrySelect.value;
        }
        
        if (maxAirportsSelect.value) {
            this.currentFilters.max_airports = parseInt(maxAirportsSelect.value);
        }
        
        if (hasProceduresCheckbox.checked) {
            this.currentFilters.has_procedures = true;
        }
        
        if (hasAIPDataCheckbox.checked) {
            this.currentFilters.has_aip_data = true;
        }
        
        if (hasHardRunwayCheckbox.checked) {
            this.currentFilters.has_hard_runway = true;
        }
        
        if (borderCrossingCheckbox.checked) {
            this.currentFilters.point_of_entry = true;
        }
        
        // Restore AIP field filters if they were previously set
        if (aipField) {
            this.currentFilters.aip_field = aipField;
            this.currentFilters.aip_value = aipValue;
            this.currentFilters.aip_operator = aipOperator;
        }
    }

    applyAIPPreset(preset) {
        // Clear any existing custom AIP filter
        this.clearCustomAIPFilter();
        
        // Apply the preset
        this.currentFilters.aip_field = preset.field;
        this.currentFilters.aip_value = preset.value;
        this.currentFilters.aip_operator = preset.operator;
        
        // Update UI to show active preset
        this.updateActiveAIPFilterDisplay(preset.name, preset.icon);
        
        // Apply filters
        this.applyFilters();
    }

    applyCustomAIPFilter() {
        const fieldSelect = document.getElementById('aip-field-select');
        const operatorSelect = document.getElementById('aip-operator-select');
        const valueInput = document.getElementById('aip-value-input');
        
        const field = fieldSelect.value;
        const operator = operatorSelect.value;
        const value = valueInput.value.trim();
        
        if (!field) {
            return;
        }
        
        // Clear any existing preset
        this.clearAIPPresetSelection();
        
        // Apply custom filter
        this.currentFilters.aip_field = field;
        this.currentFilters.aip_value = value || null;
        this.currentFilters.aip_operator = operator;
        
        // Update UI
        const displayText = this.getAIPFilterDisplayText(field, operator, value);
        this.updateActiveAIPFilterDisplay(displayText);
        
        // Apply filters
        this.applyFilters();
    }

    clearAIPFilter() {
        this.currentFilters.aip_field = null;
        this.currentFilters.aip_value = null;
        this.currentFilters.aip_operator = null;
        
        this.clearAIPPresetSelection();
        this.clearCustomAIPFilter();
        this.hideActiveAIPFilterDisplay();
        
        this.applyFilters();
    }

    clearAIPPresetSelection() {
        const presetButtons = document.querySelectorAll('.aip-preset-btn');
        presetButtons.forEach(btn => btn.classList.remove('active'));
    }

    clearCustomAIPFilter() {
        const fieldSelect = document.getElementById('aip-field-select');
        const operatorSelect = document.getElementById('aip-operator-select');
        const valueInput = document.getElementById('aip-value-input');
        
        fieldSelect.value = '';
        operatorSelect.value = 'contains';
        valueInput.value = '';
    }

    updateActiveAIPFilterDisplay(text, icon = '') {
        const displayDiv = document.getElementById('active-aip-filter');
        const textSpan = document.getElementById('active-aip-filter-text');
        
        textSpan.innerHTML = icon ? `${icon} ${text}` : text;
        displayDiv.style.display = 'block';
    }

    hideActiveAIPFilterDisplay() {
        const displayDiv = document.getElementById('active-aip-filter');
        displayDiv.style.display = 'none';
    }

    getAIPFilterDisplayText(field, operator, value) {
        if (operator === 'not_empty') {
            return `${field} is not empty`;
        } else if (value) {
            return `${field} ${operator} "${value}"`;
        } else {
            return `${field} ${operator}`;
        }
    }

    async applyFilters() {
        try {
            this.showLoading();
            
            // Update filters from UI
            this.updateFilters();
            
            console.log('applyFilters - currentRoute:', this.currentRoute);
            console.log('applyFilters - currentFilters:', this.currentFilters);
            
            // Check if we have an active route search AND it's not null
            if (this.currentRoute && this.currentRoute.airports && this.currentRoute.airports.length > 0) {
                console.log('applyFilters - Reapplying route search with new filters');
                // Reapply route search with current filters
                await this.handleRouteSearch(this.currentRoute.airports, true);
                return;
            }
            
            // Regular filter application (no active route)
            console.log('applyFilters - Applying regular filters to all airports');
            
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
            // Reset the apply button state after auto-apply
            this.resetApplyButton();
        }
    }

    resetApplyButton() {
        const applyButton = document.getElementById('apply-filters');
        applyButton.innerHTML = '<i class="fas fa-search"></i> Apply Filters';
        applyButton.disabled = false;
    }

    async handleSearch(query) {
        console.log('handleSearch - Input query:', query);
        
        // Trim the query
        query = query.trim();
        
        // If query is empty, reset to show all airports
        if (!query) {
            console.log('handleSearch - Empty query, resetting to all airports');
            this.clearFilters();
            return;
        }
        
        // Check if this is a route search
        const routeAirports = this.parseRouteFromQuery(query);
        console.log('handleSearch - Route airports detected:', routeAirports);
        
        if (routeAirports) {
            console.log('handleSearch - Executing route search');
            await this.handleRouteSearch(routeAirports);
        } else {
            console.log('handleSearch - Executing regular text search');
            try {
                this.showLoading();
                
                // Update filters from UI
                this.updateFilters();
                
                // Search for airports
                const airports = await api.searchAirports(query, 50);
                
                // Use the same unified airport handling as route search
                this.updateMapWithAirports(airports, false);
                
                // Update statistics
                this.updateStatistics(airports);
                
                // Show success message
                this.showSuccess(`Search results: ${airports.length} airports found for "${query}"`);
                
            } catch (error) {
                console.error('Error in search:', error);
                this.showError('Error searching airports: ' + error.message);
            } finally {
                this.hideLoading();
                this.resetApplyButton();
            }
        }
        
        // Update URL after search
        this.updateURL();
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
        
        if (allIcaoCodes && parts.length >= 1) {
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
            console.log('handleRouteSearch - Route airports:', routeAirports);
            console.log('handleRouteSearch - skipFilterUpdate:', skipFilterUpdate);
            
            // Search for airports near the route with filters
            const routeResults = await api.searchAirportsNearRoute(routeAirports, distanceNm, currentFilters);
            
            console.log('handleRouteSearch - Route results:', routeResults);
            
            // Extract airport data for unified handling
            const airports = routeResults.airports.map(item => ({
                ...item.airport,
                // Add route-specific data as custom properties
                _routeDistance: item.distance_nm,
                _closestSegment: item.closest_segment
            }));
            
            console.log('handleRouteSearch - Extracted airports:', airports);
            console.log('handleRouteSearch - Route airports in results:', routeAirports.map(icao => airports.find(a => a.ident === icao)));
            
            // Use the same unified airport handling as normal mode
            this.updateMapWithAirports(airports, false);
            
            // Get original route airport data for route line drawing
            let originalRouteAirports;
            
            if (skipFilterUpdate && this.currentRoute && this.currentRoute.originalRouteAirports) {
                // Use stored original data when reapplying filters
                console.log('Using stored original route airport data for route line');
                originalRouteAirports = this.currentRoute.originalRouteAirports;
            } else {
                // For new route searches, we need to get the complete route airport data
                // regardless of filters to ensure the route line is always complete
                console.log('Getting complete route airport data for new route search');
                
                // Get route airport data without filters to ensure completeness
                const unfilteredRouteResults = await api.searchAirportsNearRoute(routeAirports, distanceNm, {});
                const unfilteredAirports = unfilteredRouteResults.airports.map(item => item.airport);
                
                originalRouteAirports = routeAirports.map(icao => {
                    const airport = unfilteredAirports.find(a => a.ident === icao);
                    if (airport) {
                        return {
                            icao: icao,
                            lat: airport.latitude_deg,
                            lng: airport.longitude_deg
                        };
                    }
                    console.error(`Route airport ${icao} not found in unfiltered results!`);
                    return null;
                }).filter(a => a !== null);
                
                console.log('Complete route airport data calculated:', originalRouteAirports);
            }
            
            console.log('Original route airports for line drawing:', originalRouteAirports);
            
            // Display the route on the map (after airports are added)
            // Pass original route airport data to ensure complete route line
            airportMap.displayRoute(routeAirports, distanceNm, skipFilterUpdate, originalRouteAirports);
            
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
                results: routeResults,
                originalRouteAirports: originalRouteAirports // Store for route line drawing
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
        // Note: Apply button state is now handled separately in resetApplyButton()
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

    // Apply filters from URL parameters (without updating URL)
    async applyFiltersFromURL() {
        console.log('Applying filters from URL parameters');
        
        // Build current filters from form elements
        this.currentFilters = {};
        
        // Country filter
        const country = document.getElementById('country-filter').value;
        if (country) {
            this.currentFilters.country = country;
        }
        
        // Boolean filters
        const booleanFilters = [
            { id: 'has-procedures', key: 'has_procedures' },
            { id: 'has-aip-data', key: 'has_aip_data' },
            { id: 'has-hard-runway', key: 'has_hard_runway' },
            { id: 'border-crossing-only', key: 'point_of_entry' }
        ];
        
        for (const filter of booleanFilters) {
            const element = document.getElementById(filter.id);
            if (element && element.checked) {
                this.currentFilters[filter.key] = true;
            }
        }
        
        // Max airports
        const maxAirports = document.getElementById('max-airports-filter').value;
        if (maxAirports) {
            this.currentFilters.limit = parseInt(maxAirports);
        }
        
        // Apply the filters
        await this.applyFilters();
    }

    // Update URL with current configuration
    updateURL() {
        const params = new URLSearchParams();
        
        // Add country filter
        const country = document.getElementById('country-filter').value;
        if (country) {
            params.set('country', country);
        }
        
        // Add boolean filters
        const booleanFilters = [
            { id: 'has-procedures', param: 'has_procedures' },
            { id: 'has-aip-data', param: 'has_aip_data' },
            { id: 'has-hard-runway', param: 'has_hard_runway' },
            { id: 'border-crossing-only', param: 'border_crossing_only' }
        ];
        
        for (const filter of booleanFilters) {
            const element = document.getElementById(filter.id);
            if (element && element.checked) {
                params.set(filter.param, 'true');
            }
        }
        
        // Add search/route
        const search = document.getElementById('search-input').value;
        if (search) {
            params.set('search', encodeURIComponent(search));
        }
        
        // Add route distance
        const routeDistance = document.getElementById('route-distance').value;
        if (routeDistance && routeDistance !== '50') {
            params.set('route_distance', routeDistance);
        }
        
        // Add max airports
        const maxAirports = document.getElementById('max-airports-filter').value;
        if (maxAirports && maxAirports !== '1000') {
            params.set('max_airports', maxAirports);
        }
        
        // Add legend mode
        const legendMode = document.getElementById('legend-mode-filter').value;
        if (legendMode && legendMode !== 'airport-type') {
            params.set('legend', legendMode);
        }
        
        // Add map settings if available
        if (airportMap && airportMap.map) {
            const center = airportMap.map.getCenter();
            const zoom = airportMap.map.getZoom();
            params.set('center', `${center.lat.toFixed(4)},${center.lng.toFixed(4)}`);
            params.set('zoom', zoom.toString());
        }
        
        // Update URL without page reload
        const newURL = window.location.origin + window.location.pathname + 
                      (params.toString() ? '?' + params.toString() : '');
        window.history.replaceState({}, '', newURL);
        
        console.log('Updated URL:', newURL);
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
        console.log('clearFilters - Starting clear operation');
        console.log('clearFilters - currentRoute before clear:', this.currentRoute);
        
        // Clear current route FIRST to prevent auto-apply from using it
        this.currentRoute = null;
        console.log('clearFilters - currentRoute cleared immediately:', this.currentRoute);
        
        // Clear all filter inputs
        document.getElementById('country-filter').value = '';
        document.getElementById('has-procedures').checked = false;
        document.getElementById('has-aip-data').checked = false;
        document.getElementById('has-hard-runway').checked = false;
        document.getElementById('border-crossing-only').checked = false;
        
        // Clear AIP filters
        this.clearAIPFilter();
        
        // Clear search input
        document.getElementById('search-input').value = '';
        
        // Reset current filters
        this.currentFilters = {};
        
        // Clear the route line from the map
        airportMap.clearRoute();
        
        // Load all airports without filters (don't call applyFilters to avoid recursion)
        this.loadAllAirports();
    }

    async loadAllAirports() {
        try {
            this.showLoading();
            
            // Load all airports without any filters
            const airports = await api.getAirports({});
            
            // Update map with all airports
            this.updateMapWithAirports(airports, false);
            
            // Update statistics
            this.updateStatistics(airports);
            
            // Show success message
            this.showSuccess(`Loaded all airports: ${airports.length} airports`);
            
        } catch (error) {
            console.error('Error loading all airports:', error);
            this.showError('Error loading airports: ' + error.message);
        } finally {
            this.hideLoading();
            this.resetApplyButton();
        }
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
            
            // Store current route information before clearing markers
            const currentRoute = this.currentRoute;
            
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
                
                // Redraw route if there was an active route
                if (currentRoute && currentRoute.airports) {
                    console.log('Redrawing route after legend mode change');
                    airportMap.displayRoute(
                        currentRoute.airports, 
                        currentRoute.distance_nm, 
                        true, // preserve view
                        currentRoute.originalRouteAirports
                    );
                }
            }
        }
        
        // Update URL after legend mode change
        this.updateURL();
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