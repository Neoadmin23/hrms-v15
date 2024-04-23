<template>
	<div class="flex flex-col bg-white rounded w-full py-6 px-4 border-none">
		<h2 class="text-lg font-bold text-gray-900">
			Hey, {{ employee?.data?.first_name }} 👋
		</h2>

		<template v-if="allowCheckinFromMobile.data">
			<div class="font-medium text-sm text-gray-500 mt-1.5" v-if="lastLog">
				Last {{ lastLogType }} was at {{ lastLogTime }}
			</div>
			<div class="mt-4">
				<select
					v-model="selectedOfficeAddress"
					@change="fetchOfficeLocation"
					class="border-gray-300 rounded-md shadow-sm"
				>
					<option disabled value="">Select an office address</option>
					<option
						v-for="address in officeAddresses"
						:key="address.name"
						:value="address.name"
					>
						{{ address.address_title }}
					</option>
				</select>
			</div>
			<Button
				class="mt-4 mb-1 drop-shadow-sm py-5 text-base"
				id="open-checkin-modal"
				@click="checkinTimestamp = dayjs().format('YYYY-MM-DD HH:mm:ss')"
			>
				<template #prefix>
					<FeatherIcon
						:name="
							nextAction.action === 'IN'
								? 'arrow-right-circle'
								: 'arrow-left-circle'
						"
						class="w-4"
					/>
				</template>
				{{ nextAction.label }}
			</Button>

			<ion-modal
				ref="modal"
				trigger="open-checkin-modal"
				:initial-breakpoint="1"
				:breakpoints="[0, 1]"
				@ionModalDidPresent="onModalDidPresent"
			>
				<div
					class="h-500 w-full flex flex-col items-center justify-center gap-5 p-4 mb-5"
				>
					<div
						id="map"
						style="
							height: 300px;
							width: 100%;
							margin-bottom: 20px;
							border-radius: 10px;
							background-color: #f0f0f0;
							box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1),
								0 1px 3px rgba(0, 0, 0, 0.08); /* Elevation and shadow */
						"
					></div>
					<div class="flex flex-col gap-1.5 items-center justify-center">
						<div class="font-bold text-xl">
							{{ dayjs(checkinTimestamp).format("hh:mm:ss a") }}
						</div>
						<div class="font-medium text-gray-500 text-sm">
							{{ dayjs().format("D MMM, YYYY") }}
						</div>
					</div>
					<Button
						variant="solid"
						class="w-full py-5 text-sm"
						@click="captureAndSubmitLog(nextAction.action)"
					>
						Confirm {{ nextAction.label }}
					</Button>
				</div>
			</ion-modal>
		</template>

		<div v-else class="font-medium text-sm text-gray-500 mt-1.5">
			{{ dayjs().format("ddd, D MMMM, YYYY") }}
		</div>
	</div>
</template>

<script setup>
import {
	createListResource,
	toast,
	FeatherIcon,
	createResource,
} from "frappe-ui"
import {
	computed,
	inject,
	ref,
	onMounted,
	onBeforeUnmount,
	nextTick,
} from "vue"
import { IonModal, modalController } from "@ionic/vue"
import { allowCheckinFromMobile } from "@/data/settings"

const DOCTYPE = "Employee Checkin"

const socket = inject("$socket")
const employee = inject("$employee")
const dayjs = inject("$dayjs")
const checkinTimestamp = ref(null)

const map = ref(null) // Holds the Google Maps instance
const mapInitialized = ref(false)

const checkins = createListResource({
	doctype: DOCTYPE,
	fields: [
		"name",
		"employee",
		"employee_name",
		"log_type",
		"time",
		"device_id",
	],
	filters: {
		employee: employee.data.name,
	},
	orderBy: "time desc",
})
checkins.reload()

const lastLog = computed(() => {
	if (checkins.list.loading || !checkins.data) return {}
	return checkins.data[0]
})

const lastLogType = computed(() => {
	return lastLog?.value?.log_type === "IN" ? "check-in" : "check-out"
})

const nextAction = computed(() => {
	return lastLog?.value?.log_type === "IN"
		? { action: "OUT", label: "Check Out" }
		: { action: "IN", label: "Check In" }
})

const lastLogTime = computed(() => {
	const timestamp = lastLog?.value?.time
	const formattedTime = dayjs(timestamp).format("hh:mm a")

	if (dayjs(timestamp).isToday()) return formattedTime
	else if (dayjs(timestamp).isYesterday()) return `${formattedTime} yesterday`
	else if (dayjs(timestamp).isSame(dayjs(), "year"))
		return `${formattedTime} on ${dayjs(timestamp).format("D MMM")}`

	return `${formattedTime} on ${dayjs(timestamp).format("D MMM, YYYY")}`
})

const captureAndSubmitLog = (logType) => {
	if (navigator.geolocation) {
		navigator.geolocation.getCurrentPosition(
			(position) => {
				const userLocation = {
					latitude: position.coords.latitude,
					longitude: position.coords.longitude,
				}
				const distance = calculateDistance(
					userLocation.latitude,
					userLocation.longitude,
					officeLocation.value.latitude,
					officeLocation.value.longitude
				)

				if (distance <= allowedRadius.value) {
					// User is within the allowed radius, proceed to submit the log
					submitLog(logType, userLocation.latitude, userLocation.longitude)
				} else {
					// User is outside the allowed radius
					const distanceOutside = (
						(distance - allowedRadius.value) /
						1000
					).toFixed(2) // Convert to kilometers and round to 2 decimal places
					toast({
						title: "Location Error",
						text: `You are ${distanceOutside} km too far from the office. You must be within ${
							allowedRadius.value / 1000
						} km to check-in or check-out.`,
						icon: "alert-circle",
						position: "top-center",
						iconClasses: "text-red-500",
					})
				}
			},
			(error) => {
				console.error(error)
				toast({
					title: "Geolocation Error",
					text: "Failed to retrieve your location. Please allow location access and try again.",
					icon: "alert-circle",
					position: "top-center",
					iconClasses: "text-red-500",
				})
			},
			{ enableHighAccuracy: true }
		)
	} else {
		// Geolocation is not supported by this browser
		toast({
			title: "Unsupported Feature",
			text: "Geolocation is not supported by your browser.",
			icon: "info",
			position: "bottom-center",
			iconClasses: "text-blue-500",
		})
	}
}

function calculateDistance(lat1, lon1, lat2, lon2) {
	console.log("calculate distance parameters :: ", lat1, lon1, lat2, lon2)
	if ([lat1, lon1, lat2, lon2].some((coord) => isNaN(parseFloat(coord)))) {
		console.error(
			"Invalid input for distance calculation:",
			lat1,
			lon1,
			lat2,
			lon2
		)
		return NaN // or handle error as appropriate
	} else {
		const R = 6371e3 // Earth radius in meters
		const φ1 = (lat1 * Math.PI) / 180
		const φ2 = (lat2 * Math.PI) / 180
		const Δφ = ((lat2 - lat1) * Math.PI) / 180
		const Δλ = ((lon2 - lon1) * Math.PI) / 180

		const a =
			Math.sin(Δφ / 2) * Math.sin(Δφ / 2) +
			Math.cos(φ1) * Math.cos(φ2) * Math.sin(Δλ / 2) * Math.sin(Δλ / 2)
		const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a))
		console.log("Distance Calculated :: ", R * c)
		return R * c // Distance in meters
	}
}

const submitLog = (logType, latitude = null, longitude = null) => {
	const action = logType === "IN" ? "Check-in" : "Check-out"

	checkins.insert.submit(
		{
			employee: employee.data.name,
			log_type: logType,
			time: checkinTimestamp.value,
			latitude,
			longitude,
			address: officeAddressDocData.value.name,
			address_latitude: officeLocation.value.latitude,
			address_longitude: officeLocation.value.longitude,
			radius: allowedRadius.value,
			city: officeAddressDocData.value.city,
			state: officeAddressDocData.value.state,
			area: officeAddressDocData.value.area,
		},
		{
			onSuccess() {
				modalController.dismiss()
				toast({
					title: "Success",
					text: `${action} successful!`,
					icon: "check-circle",
					position: "bottom-center",
					iconClasses: "text-green-500",
				})
			},
			onError() {
				toast({
					title: "Error",
					text: `${action} failed!`,
					icon: "alert-circle",
					position: "bottom-center",
					iconClasses: "text-red-500",
				})
			},
		}
	)
}

const initMap = async (userLat, userLng, officeLat, officeLng) => {
	await nextTick() // Ensure the DOM is updated

	console.log("initMap :: ", userLat, userLng, officeLat, officeLng)
	// Ensure the map div is accessible
	const mapElement = document.getElementById("map")
	if (!mapElement) {
		console.error("Map container not found.")
		return
	}
	if (mapElement && !mapInitialized.value) {
		// Initialize the map
		const { Map } = await google.maps.importLibrary("maps")
		const map = new Map(mapElement, {
			zoom: 13,
			center: new google.maps.LatLng(officeLat, officeLng),
			mapId: "4504f8b37365c3d0",
		})
		const { AdvancedMarkerElement, PinElement } =
			await google.maps.importLibrary("marker")

		// Add markers for the office and user locations
		const pinBackground = new PinElement({
			background: "#7ea0f7",
			glyphColor: "white",
			borderColor: "black",
		})
		new AdvancedMarkerElement({
			position: { lat: officeLat, lng: officeLng },
			map: map,
			title: "Office Location",
			content: pinBackground.element,
		})

		new AdvancedMarkerElement({
			position: { lat: userLat, lng: userLng },
			map: map,
			title: "Your Location",
		})

		// Optional: Add a circle to visualize the radius
		new google.maps.Circle({
			strokeColor: "#3333ff",
			strokeOpacity: 0.8,
			strokeWeight: 2,
			fillColor: "#9999ff",
			fillOpacity: 0.35,
			map: map,
			center: new google.maps.LatLng(officeLat, officeLng),
			radius: parseInt(allowedRadius.value), // Radius in meters
		})
		mapInitialized.value = true
	}
}
const officeLocation = ref({ latitude: null, longitude: null })
const allowedRadius = ref(null)
const mapsAPIKey = ref(null)
const userLatitude = ref(null)
const userLongitude = ref(null)
const errorMessage = ref("")
const officeAddressDocData = ref({ name: "", city: "", state: "", area: "" })

onMounted(async () => {
	// Fetch Geo Location Settings
	await fetchGeoLocationSettings.reload()

	// Fetch office addresses
	await fetchOfficeAddresses.reload()

	socket.emit("doctype_subscribe", DOCTYPE)
	socket.on("list_update", (data) => {
		if (data.doctype == DOCTYPE) {
			checkins.reload()
		}
	})
})

const onModalDidPresent = async () => {
	mapInitialized.value = false
	await nextTick()
	loadGoogleMapsScript(mapsAPIKey.value)
		.then(() => {
			console.log("Google Maps script loaded successfully.")
			fetchUserLocation()
			// You can now initialize your map or set a flag that it's ready
		})
		.catch((error) => console.error("Error loading Google Maps script:", error))
}

const loadGoogleMapsScript = (apiKey) => {
	return new Promise((resolve, reject) => {
		// Check if script is already loaded
		if (window.google && window.google.maps) {
			resolve()
			fetchUserLocation()
			return
		}

		const script = document.createElement("script")
		script.src = `https://maps.googleapis.com/maps/api/js?key=${apiKey}&callback=initGoogleMaps`
		script.async = true
		script.defer = true

		window.initGoogleMaps = () => {
			console.log("Google Maps API is ready.")
			console.log("Office locations :: ", officeLocation.value)
			fetchUserLocation().then(() => {
				console.log(
					"User location :: ",
					userLatitude.value,
					userLongitude.value
				)
				console.log(
					"Office location :: ",
					officeLocation.value.latitude,
					officeLocation.value.longitude
				)
			})
			resolve()
		} // Callback function to resolve the promise

		script.onerror = (error) => reject(error)

		document.head.appendChild(script)
	})
}

const fetchGeoLocationSettings = createResource({
	// Make an API call to your backend method to fetch geo location settings
	url: "hrms.api.get_geo_location_settings",
	onSuccess(data) {
		console.log("geo settings response :: ", data)
		allowedRadius.value = data.radius
		mapsAPIKey.value = data.api_key
	},
})

const fetchUserLocation = async () => {
	if (navigator.geolocation) {
		navigator.geolocation.getCurrentPosition(
			(position) => {
				userLatitude.value = position.coords.latitude
				userLongitude.value = position.coords.longitude
				// You can call any function here to use the latitude and longitude
				console.log(
					`Latitude: ${userLatitude.value}, Longitude: ${userLongitude.value}`
				)
				if (
					userLatitude.value &&
					userLongitude.value &&
					officeLocation.value.latitude &&
					officeLocation.value.longitude
				) {
					console.log("User and office locations are available.")
					initMap(
						userLatitude.value,
						userLongitude.value,
						officeLocation.value.latitude,
						officeLocation.value.longitude
					)
				}
			},
			(error) => {
				// Handle errors here
				switch (error.code) {
					case error.PERMISSION_DENIED:
						errorMessage.value = "User denied the request for Geolocation."
						break
					case error.POSITION_UNAVAILABLE:
						errorMessage.value = "Location information is unavailable."
						break
					case error.TIMEOUT:
						errorMessage.value = "The request to get user location timed out."
						break
					case error.UNKNOWN_ERROR:
						errorMessage.value = "An unknown error occurred."
						break
				}
				console.error(errorMessage.value)
			},
			{ enableHighAccuracy: true }
		)
	} else {
		errorMessage.value = "Geolocation is not supported by this browser."
		console.error(errorMessage.value)
	}
}

onBeforeUnmount(() => {
	socket.emit("doctype_unsubscribe", DOCTYPE)
	socket.off("list_update")
})

// office address list selection
// Add these reactive properties
const officeAddresses = ref([]) // To store the list of office addresses
const selectedOfficeAddress = ref("") // To store the selected office address

// Fetch office addresses from the backend
const fetchOfficeAddresses = createResource({
	url: "/api/method/hrms.api.office_address_list",

	onSuccess(response) {
		console.log("Office addresses fetched :: ", response)
		officeAddresses.value = response
	},
	onError(error) {
		console.error("Failed to fetch office addresses:", error)
		toast({
			title: "Error",
			text: "Failed to fetch office addresses.",
			icon: "alert-circle",
			position: "bottom-center",
			iconClasses: "text-red-500",
		})
	},
})

const fetchOfficeLocation = async () => {
	const selectedAddress = officeAddresses.value.find(
		(address) => address.name === selectedOfficeAddress.value
	)
	if (!selectedAddress) return
	const officeAddressDocName = selectedAddress.name
	console.log("Selected office address :: ", officeAddressDocName)

	// loop through officeAddresses and find the selected address latitude and longitude
	officeAddresses.value.forEach((address) => {
		console.log("Address :: ", address)
		if (address.name === officeAddressDocName) {
			officeLocation.value.latitude = parseFloat(address.latitude)
			officeLocation.value.longitude = parseFloat(address.longitude)
			officeAddressDocData.value.name = officeAddressDocName
			officeAddressDocData.value.city = address.city
			officeAddressDocData.value.state = address.state
			officeAddressDocData.value.area = address.county
		}
	})
}
</script>
