<template>
  <Tabs
    :modelValue="tabIndex"
    :tabs="tabs"
    @update:modelValue="changeTabTo"
    class="[&_[role='tab']]:px-0 [&_[role='tablist']]:px-5 [&_[role='tablist']]:gap-7.5 [&_[role='tablist']]:flex-shrink-0"
  >
    <template #tab-panel="{ tab }">
      <TicketAgentActivities
        v-if="Boolean(activities.data)"
        ref="ticketAgentActivitiesRef"
        :activities="filterActivities(tab.name as TicketTab)"
        :title="tab.label"
        :ticket-status="ticket.doc.status"
        @email:reply="
          (e) => {
            communicationAreaRef.replyToEmail(e);
          }
        "
        @update="
          () => {
            activities.reload();
            ticketAgentActivitiesRef.scrollToLatestActivity();
          }
        "
      />
      <div v-else class="flex items-center justify-center flex-col mt-20">
        <LoadingIndicator :scale="8" class="text-ink-gray-5" />
        <p class="text-xl font-medium text-ink-gray-5 absolute top-[50%]">
          Loading...
        </p>
      </div>
    </template>
  </Tabs>
  <!-- Comm Area -->
  <CommunicationArea
    ref="communicationAreaRef"
    :ticketId="String(ticket.doc?.name)"
    :to-emails="[ticket.doc?.raised_by]"
    :cc-emails="[]"
    :bcc-emails="[]"
    :last-email="lastEmail"
    :key="ticket.doc?.name"
    @update="
      () => {
        activities.reload();
        ticketAgentActivitiesRef.scrollToLatestActivity();
      }
    "
  />
</template>

<script setup lang="ts">
import {
  ActivityIcon,
  CommentIcon,
  EmailIcon,
  PhoneIcon,
} from "@/components/icons";
import { useActiveTabManager } from "@/composables/useActiveTabManager";
import { useTelephonyStore } from "@/stores/telephony";
import {
  ActivitiesSymbol,
  FeedbackActivity,
  TabObject,
  TicketSymbol,
  TicketTab,
} from "@/types";
import { createResource, LoadingIndicator, Tabs } from "frappe-ui";
import { storeToRefs } from "pinia";
import { computed, ComputedRef, defineAsyncComponent, inject, ref } from "vue";
// import { extractBareEmail, normalizeEmailList } from "@/utils";
import TicketAgentActivities from "../ticket/TicketAgentActivities.vue";

const CommunicationArea = defineAsyncComponent(
  () => import("@/components/CommunicationArea.vue")
);

// // Fetch all outgoing email addresses configured in the system so we can
// // exclude them from reply recipients (prevent emailing our own helpdesk inbox)
// const outgoingEmailsResource = createResource({
//   url: "helpdesk.api.doc.get_outgoing_email_addresses",
//   auto: true,
// });
// const outgoingEmails = computed<Set<string>>(() => {
//   const list: string[] = outgoingEmailsResource.data || [];
//   return new Set(list.map((e) => e.toLowerCase().trim()));
// });

const ticket = inject(TicketSymbol);
const activities = inject(ActivitiesSymbol);

const ticketAgentActivitiesRef = ref(null);
const communicationAreaRef = ref(null);
const telephonyStore = useTelephonyStore();
const { isCallingEnabled } = storeToRefs(telephonyStore);

const tabs: ComputedRef<TabObject[]> = computed(() => {
  const _tabs: TabObject[] = [
    {
      name: "activity",
      label: "Activity",
      icon: ActivityIcon,
    },
    {
      name: "email",
      label: "Emails",
      icon: EmailIcon,
    },
    {
      name: "comment",
      label: "Comments",
      icon: CommentIcon,
    },
  ];

  if (isCallingEnabled.value) {
    _tabs.push({
      name: "call",
      label: "Calls",
      icon: PhoneIcon,
    });
  }
  return _tabs;
});

const { tabIndex, changeTabTo } = useActiveTabManager(tabs);

// TODO: refactor for pagination
// can be done once we sort out the backend
const _activities = computed(() => {
  if (!activities.value?.data) {
    return [];
  }

  const emailProps = activities.value?.data?.communications.map(
    (email, idx: number) => {
      return {
        subject: email.subject,
        content: email.content,
        sender: { name: email.user.email, full_name: email.user.name },
        to: email.recipients,
        type: "email",
        key: email.creation,
        cc: email.cc,
        bcc: email.bcc,
        creation: email.communication_date || email.creation,
        attachments: email.attachments,
        name: email.name,
        deliveryStatus: email.delivery_status,
        isFirstEmail: idx === 0,
      };
    }
  );

  const commentProps = activities.value.data.comments.map((comment) => {
    return {
      name: comment.name,
      type: "comment",
      key: comment.creation,
      commentedBy: comment.commented_by,
      commenter: comment.user.name,
      creation: comment.creation,
      content: comment.content,
      attachments: comment.attachments,
    };
  });

  const historyProps = [
    ...activities.value.data.history,
    ...activities.value.data.views,
  ].map((h) => {
    return {
      type: "history",
      key: h.creation,
      content: h.action ? h.action : "viewed this",
      creation: h.creation,
      user: h.user.name + " ",
    };
  });

  const callProps = activities.value.data.calls.map((call) => {
    return {
      ...call,
      type: "call",
      name: call.name,
      key: call.creation,
      call_type: call.type,
      content: `${call.caller || "Unknown"} made a call to ${
        call.receiver || "Unknown"
      }`,
      duration: call.duration ? call.duration + "s" : "0s",
    };
  });

  const sorted = [
    ...emailProps,
    ...commentProps,
    ...historyProps,
    ...callProps,
  ].sort((a, b) => new Date(a.creation) - new Date(b.creation));
  const data = [];
  let i = 0;

  while (i < sorted.length) {
    const currentActivity = sorted[i];

    if (currentActivity.type === "history") {
      currentActivity.relatedActivities = [currentActivity];
      for (let j = i + 1; j < sorted.length + 1; j++) {
        const nextActivity = sorted[j];

        if (
          nextActivity &&
          nextActivity.user === currentActivity.user &&
          nextActivity.content !== "viewed this" &&
          !nextActivity.content.includes("assigned") &&
          !nextActivity.content.includes("unassigned")
        ) {
          currentActivity.relatedActivities.push(nextActivity);
        } else {
          data.push(currentActivity);
          i = j - 1;
          break;
        }
      }
    } else {
      data.push(currentActivity);
    }
    i++;
  }
  // add feedback data at the last always
  // name is email
  // full_name is name

  if (ticket.value.doc.feedback_rating === 0) {
    return data;
  }
  let feedbackActivity: FeedbackActivity[] = [
    {
      type: "feedback",
      key: "feedback-activity",
      feedback_rating: ticket.value?.doc.feedback_rating,
      feedback_extra: ticket.value?.doc.feedback_extra,
      feedback: ticket.value?.doc.feedback,
      sender: {
        name: ticket.value?.doc.raised_by,
        full_name: ticket.value?.doc.contact,
      },
    },
  ];
  data.push(...feedbackActivity);

  return data;
});

const lastEmail = computed(() => {
  const emails = _activities.value.filter((a) => a.type === "email");
  return emails.length ? emails[emails.length - 1] : null;
});

function filterActivities(eventType: TicketTab) {
  if (eventType === "activity") {
    return _activities.value;
  }
  return _activities.value.filter((activity) => activity.type === eventType);
}

// const threadCcEmails = computed(() => {
//   if (!activities.value?.data?.communications) return [];

//   const raisedBy = extractBareEmail(ticket.value?.doc?.raised_by || "");

//   // Exclude: ticket raiser (goes in TO) and all outgoing helpdesk addresses
//   const excludeEmails = new Set<string>(outgoingEmails.value);
//   if (raisedBy) excludeEmails.add(raisedBy);

//   const ccSet = new Set<string>();

//   for (const email of activities.value.data.communications as any[]) {
//     for (const addr of normalizeEmailList(email.cc)) {
//       if (!excludeEmails.has(addr)) ccSet.add(addr);
//     }
//     // Only pull recipients from SENT emails — received recipients are the
//     // helpdesk inbox address and must never be CC'd back.
//     if (email.sent_or_received === "Sent") {
//       for (const addr of normalizeEmailList(email.recipients)) {
//         if (!excludeEmails.has(addr)) ccSet.add(addr);
//       }
//     }
//   }

//   // Include original CC stored on the ticket doc
//   for (const addr of normalizeEmailList(
//     ticket.value?.doc?.custom_original_cc
//   )) {
//     if (!excludeEmails.has(addr)) ccSet.add(addr);
//   }

//   return Array.from(ccSet);
// });
</script>

<style scoped></style>
