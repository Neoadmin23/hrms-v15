<template>
    <div class="flex flex-col bg-white rounded w-full py-6 px-4 border-none">
        <h2 class="text-lg font-bold text-gray-900">
            {{ __("Hey, {0} 👋", [employee?.data?.first_name]) }}
        </h2>

        <template v-if="settings.data?.allow_employee_checkin_from_mobile_app">
            <div class="font-medium text-sm text-gray-500 mt-1.5" v-if="lastLog">
                <span>{{ __("Last {0} was at {1}", [__(lastLogType), formatTimestamp(lastLog.time)]) }}</span>
                <span class="whitespace-pre"> &middot; </span>
                <router-link :to="{ name: 'EmployeeCheckinListView' }" v-slot="{ navigate }">
                    <span @click="navigate" class="underline">View List</span>
                </router-link>
            </div>
            <Button
                class="mt-4 mb-1 drop-shadow-sm py-5 text-base"
                id="open-checkin-modal"
                @click="handleEmployeeCheckin"
            >
                <template #prefix>
                    <FeatherIcon
                        :name="nextAction.action === 'IN' ? 'arrow-right-circle' : 'arrow-left-circle'"
                        class="w-4"
                    />
                </template>
                {{ nextAction.label }}
            </Button>
        </template>

        <div v-else class="font-medium text-sm text-gray-500 mt-1.5">
            {{ dayjs().format("ddd, D MMMM, YYYY") }}
        </div>
    </div>

    <ion-modal
        v-if="settings.data?.allow_employee_checkin_from_mobile_app"
        ref="modal"
        trigger="open-checkin-modal"
        :initial-breakpoint="1"
        :breakpoints="[0, 1]"
    >
        <div class="h-120 w-full flex flex-col items-center justify-center gap-5 p-4 mb-5">
            <!-- Time and Date Display -->
            <div class="flex flex-col gap-1.5 mt-2 items-center justify-center">
                <div class="font-bold text-xl">
                    {{ dayjs(checkinTimestamp).format("hh:mm:ss a") }}
                </div>
                <div class="font-medium text-gray-500 text-sm">
                    {{ dayjs().format("D MMM, YYYY") }}
                </div>
            </div>
            
            <!-- Shift Location Dropdown -->
            <div class="w-full" v-if="allowedLocations.length">
                <label for="custom_checkin_location" class="font-medium text-gray-700 text-sm">
                    {{ __("Select Shift Location") }}
                </label>
                <select
                    id="custom_checkin_location"
                    v-model="selectedLocation"
                    class="w-full mt-1 p-2 border rounded bg-white"
                    required
                >
                    <option value="" disabled>{{ __("Choose a location") }}</option>
                    <option
                        v-for="location in allowedLocations"
                        :key="location"
                        :value="location"
                    >
                        {{ location }}
                    </option>
                </select>
            </div>

            <!-- Shift Type Display (Read-Only) -->
            <div class="w-full" v-if="resolvedShiftAssignment">
                <label for="shift_type_display" class="font-medium text-gray-700 text-sm">
                    {{ __("Shift Type") }}
                </label>
                <input
                    id="shift_type_display"
                    :value="resolvedShiftAssignment.shift_type"
                    class="w-full mt-1 p-2 border rounded bg-gray-100 text-gray-700 cursor-not-allowed font-medium"
                    readonly
                />
                <!-- Hint if falling back to default -->
                <p v-if="resolvedShiftAssignment.shift_location !== selectedLocation" class="text-xs text-gray-500 mt-1">
                    {{ __("Using default shift assignment.") }}
                </p>
            </div>

            <!-- Warning if NO assignment matches and NO default exists -->
            <div v-else-if="selectedLocation && shiftTypeResource.data" class="w-full p-3 mt-2 rounded bg-yellow-50 border border-yellow-200 flex items-start gap-2 text-yellow-800 text-sm">
                <FeatherIcon name="alert-triangle" class="w-4 h-4 mt-0.5 shrink-0" />
                <div class="leading-tight font-medium">
                    {{ __("No shift assignment available!") }}
                </div>
            </div>

            <!-- Map View (Geolocation) -->
            <template v-if="settings.data?.allow_geolocation_tracking">
                <span v-if="locationStatus" class="font-medium text-gray-500 text-sm">
                    {{ locationStatus }}
                </span>

                <div class="rounded border-4 translate-z-0 block overflow-hidden w-full h-170">
                    <iframe
                        width="100%"
                        height="170"
                        frameborder="0"
                        scrolling="no"
                        marginheight="0"
                        marginwidth="0"
                        :src="`https://maps.google.com/maps?q=${latitude},${longitude}&hl=en&z=15&amp;output=embed`"
                    >
                    </iframe>
                </div>
            </template>

            <!-- Submit Button -->
            <Button
                variant="solid"
                class="w-full py-5 text-sm"
                :disabled="!selectedLocation || !allowedLocations.length"
                @click.once="submitLog(nextAction.action)"
            >
                {{ __("Confirm {0}", [nextAction.label]) }}
            </Button>
        </div>
    </ion-modal>
</template>

<script setup>
import { createResource, createListResource, toast, FeatherIcon } from "frappe-ui"
import { computed, inject, ref, onMounted, onBeforeUnmount, watch } from "vue"
import { IonModal, modalController } from "@ionic/vue"
import { formatTimestamp } from "@/utils/formatters"

const DOCTYPE = "Employee Checkin"

const socket = inject("$socket")
const employee = inject("$employee")
const dayjs = inject("$dayjs")
const __ = inject("$translate")
const checkinTimestamp = ref(null)
const latitude = ref(null)
const longitude = ref(null)
const locationStatus = ref("")
const selectedLocation = ref("")
const allowedLocations = ref([])
const shiftType = ref("")

const settings = createResource({
    url: "hrms.api.get_hr_settings",
    auto: true,
})

const checkins = createListResource({
    doctype: DOCTYPE,
    fields: ["name", "employee", "employee_name", "log_type", "time", "device_id", "custom_checkin_location"],
    filters: {
        employee: employee.data.name,
    },
    orderBy: "time desc",
    auto: false,
})

const allowedLocationsResource = createResource({
    url: "frappe.client.get",
    params: {
        doctype: "Employee",
        name: employee.data.name,
        fields: ["custom_allowed_shift_locations"],
    },
    onSuccess(data) {
        allowedLocations.value = (data.custom_allowed_shift_locations || []).map(row => row.shift_location).filter(Boolean)
        
        if (allowedLocations.value.length > 0 && !selectedLocation.value) {
            selectedLocation.value = allowedLocations.value[0]
        }
        if (selectedLocation.value && !allowedLocations.value.includes(selectedLocation.value)) {
            selectedLocation.value = allowedLocations.value[0] || ""
        }
    },
    onError(error) {
        toast({
            title: __("Error"),
            text: __("Failed to fetch allowed shift locations"),
            icon: "alert-circle",
            position: "bottom-center",
            iconClasses: "text-red-500",
        })
    },
})

const shiftTypeResource = createResource({
    url: "centralhrms.employee_checkin.get_active_shift_assignments_for_employee", 
    params: {
        employee: employee.data.name,
    },
    onSuccess(data) {
        console.log("Shift Assignments loaded:", data);
        // Note: We removed the manual shift matching from here. 
        // The availableShiftTypes computed property handles it now!
    },
    onError(error) {
        console.error("Error fetching Shift Type:", error);
        shiftType.value = ""; 
        toast({
            title: __("Error"),
            text: __("Failed to fetch Shift Type"),
            icon: "alert-circle",
            position: "bottom-center",
            iconClasses: "text-red-500",
        })
    },
})
// Determine the correct shift assignment based on location or fallback to default
const resolvedShiftAssignment = computed(() => {
    if (!shiftTypeResource.data) return null;

    // 1. Try to find an assignment specifically for the selected dropdown location
    if (selectedLocation.value) {
        const exactMatch = shiftTypeResource.data.find(
            assignment => assignment.shift_location === selectedLocation.value
        );
        if (exactMatch) return exactMatch;
    }

    // 2. FALLBACK: Look for the assignment marked as default
    const defaultMatch = shiftTypeResource.data.find(
        assignment => assignment.custom_is_default_shift === 1
    );
    
    return defaultMatch || null;
});

// Watch the resolved assignment to update the shiftType value for the submission payload
watch(resolvedShiftAssignment, (assignment) => {
    if (assignment) {
        shiftType.value = assignment.shift_type;
    } else {
        shiftType.value = "";
    }
}, { immediate: true });

// Watch for selectedLocation changes to refetch shift type
watch(selectedLocation, (newLocation) => {
    if (newLocation) {
        shiftTypeResource.fetch();
    }
})

onMounted(() => {
    checkins.fetch() 
    allowedLocationsResource.fetch()
    shiftTypeResource.fetch()
    socket.emit("doctype_subscribe", DOCTYPE)
    socket.on("list_update", (data) => {
        if (data.doctype == DOCTYPE) {
            checkins.reload()
        }
    })
})

onBeforeUnmount(() => {
    socket.emit("doctype_unsubscribe", DOCTYPE)
    socket.off("list_update")
})

const lastLog = computed(() => {
    if (checkins.list.loading || !checkins.data) return {}
    return checkins.data[0]
})

const lastLogType = computed(() => {
    return lastLog?.value?.log_type === "IN" ? "check-in" : "check-out"
})

const nextAction = computed(() => {
    return lastLog?.value?.log_type === "IN"
        ? { action: "OUT", label: __("Check Out") }
        : { action: "IN", label: __("Check In") }
})

function handleLocationSuccess(position) {
    latitude.value = position.coords.latitude
    longitude.value = position.coords.longitude
    locationStatus.value = [
        __("Latitude: {0}°", [Number(latitude.value).toFixed(5)]),
        __("Longitude: {0}°", [Number(longitude.value).toFixed(5)]),
    ].join(", ")
}

function handleLocationError(error) {
    locationStatus.value = "Unable to retrieve your location"
    if (error) locationStatus.value += `: ERROR(${error.code}): ${error.message}`
}

const fetchLocation = () => {
    if (!navigator.geolocation) {
        locationStatus.value = __("Geolocation is not supported by your current browser")
    } else {
        locationStatus.value = __("Locating...")
        navigator.geolocation.getCurrentPosition(handleLocationSuccess, handleLocationError)
    }
}

const handleEmployeeCheckin = () => {
    checkinTimestamp.value = dayjs().format("YYYY-MM-DD HH:mm:ss")
    if (settings.data?.allow_geolocation_tracking) {
        fetchLocation()
    }
    shiftTypeResource.fetch()
}

const submitLog = (logType) => {
    const actionLabel = logType === "IN" ? __("Check-in") : __("Check-out")
    const payload = {
        employee: employee.data.name,
        log_type: logType,
        time: checkinTimestamp.value,
        latitude: latitude.value,
        longitude: longitude.value,
        custom_checkin_location: selectedLocation.value,
        shift: shiftType.value,
    }

    checkins.insert.submit(
        payload,
        {
            onSuccess() {
                modalController.dismiss()
                toast({
                    title: __("Success"),
                    text: __("{0} successful!", [actionLabel]),
                    icon: "check-circle",
                    position: "bottom-center",
                    iconClasses: "text-green-500",
                })
            },
            onError(error) {
                toast({
                    title: __("Error"),
                    text: `${actionLabel} failed! ${error.messages?.[0] || ""}`,
                    icon: "alert-circle",
                    position: "bottom-center",
                    iconClasses: "text-red-500",
                })
            },
        }
    )
}
</script>