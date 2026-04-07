<template>
  <div class="comm-area">
    <div
      class="flex justify-between gap-3 border-t px-6 md:px-10 py-4 md:py-2.5"
    >
      <div class="flex gap-1.5 items-center">
        <Button
          ref="sendEmailRef"
          variant="ghost"
          label="Reply"
          :class="[showEmailBox && replyMode === 'reply' ? '!bg-gray-300 hover:!bg-gray-200' : '']"
          @click="toggleEmailBox()"
        >
          <template #prefix>
            <EmailIcon class="h-4" />
          </template>
        </Button>
        <Button
          variant="ghost"
          label="Reply All"
          :class="[showEmailBox && replyMode === 'replyAll' ? '!bg-gray-300 hover:!bg-gray-200' : '']"
          @click="toggleEmailBoxReplyAll()"
        >
          <template #prefix>
            <ReplyAllIcon class="h-4" />
          </template>
        </Button>
        <Button
          variant="ghost"
          label="Comment"
          :class="[showCommentBox ? '!bg-gray-300 hover:!bg-gray-200' : '']"
          @click="toggleCommentBox()"
        >
          <template #prefix>
            <CommentIcon class="h-4" />
          </template>
        </Button>
        <TypingIndicator :ticketId="ticketId" />
      </div>
    </div>
    <div
      ref="emailBoxRef"
      v-show="showEmailBox"
      class="flex gap-1.5 flex-1"
      @keydown.ctrl.enter.capture.stop="submitEmail"
      @keydown.meta.enter.capture.stop="submitEmail"
    >
      <EmailEditor
        ref="emailEditorRef"
        :label="
          isMobileView ? 'Send' : isMac ? 'Send (⌘ + ⏎)' : 'Send (Ctrl + ⏎)'
        "
        v-model:content="content"
        placeholder="Hi John, we are looking into this issue."
        :ticketId="ticketId"
        :to-emails="toEmails"
        :cc-emails="ccEmails"
        :bcc-emails="bccEmails"
        @submit="
          () => {
            showEmailBox = false;
            emit('update');
          }
        "
        @discard="
          () => {
            showEmailBox = false;
          }
        "
      />
    </div>
    <div
      ref="commentBoxRef"
      v-show="showCommentBox"
      @keydown.ctrl.enter.capture.stop="submitComment"
      @keydown.meta.enter.capture.stop="submitComment"
    >
      <CommentTextEditor
        ref="commentTextEditorRef"
        :label="
          isMobileView
            ? 'Comment'
            : isMac
            ? 'Comment (⌘ + ⏎)'
            : 'Comment (Ctrl + ⏎)'
        "
        :ticketId="ticketId"
        :editable="showCommentBox"
        :doctype="doctype"
        placeholder="@John could you please look into this?"
        @submit="
          () => {
            showCommentBox = false;
            emit('update');
          }
        "
        @discard="
          () => {
            showCommentBox = false;
          }
        "
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { CommentTextEditor, EmailEditor, TypingIndicator } from "@/components";
import { CommentIcon, EmailIcon, ReplyAllIcon } from "@/components/icons/";
import { useDevice } from "@/composables";
import { useScreenSize } from "@/composables/screen";
import { useShortcut } from "@/composables/shortcuts";
import { showCommentBox, showEmailBox } from "@/pages/ticket/modalStates";
import { useAuthStore } from "@/stores/auth";
import { extractBareEmail, normalizeEmailList } from "@/utils";
import { storeToRefs } from "pinia";
import { nextTick, ref, watch } from "vue";
import { onClickOutside } from "@vueuse/core";

const emit = defineEmits(["update"]);
const content = defineModel("content");
const { isMac } = useDevice();
const { isMobileView } = useScreenSize();
// let doc = inject(TicketSymbol)?.value.doc
const emailEditorRef = ref<InstanceType<typeof EmailEditor> | null>(null);
const commentTextEditorRef = ref<InstanceType<typeof CommentTextEditor> | null>(null);
const emailBoxRef = ref<HTMLElement | null>(null);
const commentBoxRef = ref<HTMLElement | null>(null);
const replyMode = ref<"reply" | "replyAll">("reply");

const { user: authUser } = storeToRefs(useAuthStore());

function buildReplyAllData(email: any) {
  const user = authUser.value;
  const senderEmail = extractBareEmail(email.sender?.name || "");

  // Normalize all address fields first, then exclude self and sender
  const filterAddrs = (field: string | string[] | null | undefined): string[] =>
    normalizeEmailList(field).filter(
      (e) => e !== user?.toLowerCase() && e !== senderEmail
    );

  const filteredTo = filterAddrs(email.to);
  const filteredCc = filterAddrs(email.cc);
  const filteredBcc = filterAddrs(email.bcc);

  if (user?.toLowerCase() === senderEmail) {
    // We sent this email — reply goes to the original recipients
    return {
      content: email.content,
      to: filteredTo,
      cc: filteredCc,
      bcc: filteredBcc,
    };
  } else {
    // We received this email — reply goes to the sender, others in CC
    const ccSeen = new Set<string>([...filteredTo, ...filteredCc]);
    return {
      content: email.content,
      to: senderEmail ? [senderEmail] : filteredTo,
      cc: Array.from(ccSeen),
      bcc: filteredBcc,
    };
  }
}

function toggleEmailBox() {
  if (showEmailBox.value && replyMode.value === "reply") {
    showEmailBox.value = false;
    return;
  }
  if (showCommentBox.value) {
    showCommentBox.value = false;
  }
  replyMode.value = "reply";
  if (props.lastEmail) {
    showEmailBox.value = true;
    nextTick(() => {
      emailEditorRef.value?.addToReply(
        props.lastEmail.content,
        props.toEmails,
        props.ccEmails,
        props.bccEmails
      );
    });
  } else {
    showEmailBox.value = true;
    nextTick(() => {
      emailEditorRef.value?.initWithSignature();
    });
  }
}

function toggleEmailBoxReplyAll() {
  if (showEmailBox.value && replyMode.value === "replyAll") {
    showEmailBox.value = false;
    return;
  }
  if (showCommentBox.value) {
    showCommentBox.value = false;
  }
  replyMode.value = "replyAll";
  if (props.lastEmail) {
    replyToEmail(buildReplyAllData(props.lastEmail));
  } else {
    showEmailBox.value = true;
  }
}

function toggleCommentBox() {
  if (showEmailBox.value) {
    showEmailBox.value = false;
  }
  showCommentBox.value = !showCommentBox.value;
}

function submitEmail() {
  if (emailEditorRef.value?.submitMail()) {
    emit("update");
  }
}

function submitComment() {
  if (commentTextEditorRef.value?.submitComment()) {
    emit("update");
  }
}



function replyToEmail(data: { content?: string; to?: string | string[]; cc?: string | string[]; bcc?: string | string[] }) {
  showEmailBox.value = true;

  // Normalize + deduplicate, then merge email-level CC with thread-wide CC
  const emailCc = normalizeEmailList(data.cc);
  const threadCc = normalizeEmailList(props.ccEmails as string[]);
  const ccSeen = new Set<string>(emailCc);
  const mergedCc = [...emailCc];
  for (const addr of threadCc) {
    if (!ccSeen.has(addr)) {
      ccSeen.add(addr);
      mergedCc.push(addr);
    }
  }

  emailEditorRef.value.addToReply(
    data.content,
    normalizeEmailList(data.to),
    mergedCc,
    normalizeEmailList(data.bcc)
  );
}

const props = defineProps({
  doctype: {
    type: String,
    default: "HD Ticket",
  },
  ticketId: {
    type: String,
    default: null,
  },
  toEmails: {
    type: Array,
    default: () => [],
  },
  ccEmails: {
    type: Array,
    default: () => [],
  },
  bccEmails: {
    type: Array,
    default: () => [],
  },
  lastEmail: {
    type: Object,
    default: null,
  },
});

watch(
  () => showEmailBox.value,
  (value) => {
    if (value) {
      emailEditorRef.value?.editor?.commands?.focus();
    }
  }
);

watch(
  () => showCommentBox.value,
  (value) => {
    if (value) {
      commentTextEditorRef.value?.editor?.commands?.focus();
    }
  }
);

useShortcut("r", () => {
  toggleEmailBox();
});
useShortcut("c", () => {
  toggleCommentBox();
});

defineExpose({
  replyToEmail,
  toggleEmailBox,
  toggleEmailBoxReplyAll,
  toggleCommentBox,
  editor: emailEditorRef,
});

onClickOutside(
  emailBoxRef,
  () => {
    if (showEmailBox.value) {
      showEmailBox.value = false;
    }
  },
  {
    ignore: [".tippy-box", ".tippy-content"],
  }
);

onClickOutside(
  commentBoxRef,
  () => {
    if (showCommentBox.value) {
      showCommentBox.value = false;
    }
  },
  {
    ignore: [".tippy-box", ".tippy-content"],
  }
);
</script>

<style>
@media screen and (max-width: 640px) {
  .comm-area {
    width: 100vw;
  }
}
</style>
