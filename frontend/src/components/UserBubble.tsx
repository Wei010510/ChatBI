interface Props {
  content: string;
}

export default function UserBubble({ content }: Props) {
  return <div className="user-bubble">{content}</div>;
}
